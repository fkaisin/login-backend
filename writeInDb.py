import csv
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator
from sqlmodel import Session, create_engine, delete, select, text
from src.db.models import Token, Transaction, User
from src.utils.security import hash_password

sqlite_url = 'sqlite:///./src/db/database.sqlite'

engine = create_engine(sqlite_url, echo=True)
with engine.begin() as conn:
    conn.execute(text('PRAGMA foreign_keys=ON'))  # for SQLite only


class TransactionCSVModel(BaseModel):
    date: datetime
    type: str
    actif_a: str
    qty_a: float
    actif_v: str | None = None
    price: float | None = None
    qty_v: float | None = None
    destination: str
    origin: str | None = None
    actif_f: str | None = None
    qty_f: float | None = None
    value_f: float | None = None
    value_a: float | None = None
    id: int | None = None

    @field_validator('date', mode='before')
    @classmethod
    def parse_date(cls, v):
        return datetime.strptime(v.strip(), '%d-%m-%y %H:%M:%S')

    @field_validator('*', mode='before')
    @classmethod
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and v.strip() == '':
            return None
        return v

    model_config = ConfigDict(extra='ignore')


def convert_transaction(tx_dict: dict) -> dict:
    validated = TransactionCSVModel(**tx_dict)
    return validated.model_dump(exclude={'id'})  # on enlève `id` s'il ne sert pas


def resetUsers():
    user1 = User(
        username='fkaisin',
        email='floriankaisin@hotmail.com',
        hashed_password=hash_password('Jtmbmu6-'),
        rank=1337,
    )
    user2 = User(
        username='ariane',
        email='ariane@hotmail.com',
        hashed_password=hash_password('Jtmbmu6-'),
    )
    user3 = User(
        username='Laure',
        email='flammecup1992@hotmail.com',
        hashed_password=hash_password('Jtmbmu6-'),
    )
    user4 = User(
        username='test',
        email='test@hotmail.com',
        hashed_password=hash_password('Jtmbmu6-'),
    )

    with Session(engine) as session:
        session.exec(delete(User))

        session.add(user1)
        session.add(user2)
        session.add(user3)
        session.add(user4)

        session.commit()


def resetTokens():
    # response_list = requests.get('https://api.coingecko.com/api/v3/coins/list')
    # coins = response_list.json()
    with open('./src/tokens.csv', 'rt', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)
    coins = [dict(zip(headers, row)) for row in rows]

    with Session(engine) as session:
        session.exec(delete(Token))

        for coin in coins:
            session.add(
                Token(cg_id=coin['cg_id'], symbol=coin['symbol'], name=coin['name'])
            )

        session.add(Token(cg_id='fiat_eur', symbol='EUR', name='Euro'))
        session.add(Token(cg_id='fiat_usd', symbol='USD', name='Dollar US'))
        session.add(Token(cg_id='fiat_cad', symbol='CAD', name='Dollar CA'))
        session.add(Token(cg_id='fiat_chf', symbol='CHF', name='Franc suisse'))
        session.commit()


def resetTransactions():
    with open('./src/transactions.csv', 'rt', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)
    transactions = [convert_transaction(dict(zip(headers, row))) for row in rows]

    with Session(engine) as session:
        fkaisin_uid = session.exec(
            select(User.uid).where(User.username == 'fkaisin')
        ).one()
        session.exec(delete(Transaction))

        for trx in transactions:
            trx['actif_a_id'] = session.exec(
                select(Token.cg_id).where(Token.symbol == trx['actif_a'])
            ).first()
            trx['actif_v_id'] = session.exec(
                select(Token.cg_id).where(Token.symbol == trx['actif_v'])
            ).first()
            trx['actif_f_id'] = session.exec(
                select(Token.cg_id).where(Token.symbol == trx['actif_f'])
            ).first()
            trx['user_id'] = fkaisin_uid
            trx.pop('actif_a', None)
            trx.pop('actif_v', None)
            trx.pop('actif_f', None)
            session.add(Transaction(**trx))
        session.commit()


def assign_transactions_to_ariane():
    with Session(engine) as session:
        user_fk = session.exec(select(User).where(User.username == 'fkaisin')).one()
        user_ak = session.exec(select(User).where(User.username == 'ariane')).one()
        statement = (
            select(Transaction).where(Transaction.user_id == user_fk.uid).limit(5)
        )
        results = session.exec(statement).all()
        for r in results:
            r.user = user_ak
            session.add(r)
        session.commit()
        for r in results:
            session.refresh(r)


def test_function():
    with Session(engine) as session:
        btc = session.get(Token, 'bitcoin')
        session.delete(btc)
        session.commit()


if __name__ == '__main__':
    resetUsers()
    resetTokens()
    resetTransactions()
    # assign_transactions_to_ariane()
    # test_function()
