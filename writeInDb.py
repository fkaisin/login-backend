import csv
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator
from sqlmodel import Session, create_engine, delete, select, text
from src.db.models import Asset, SmallToken, Token, Transaction, User
from src.utils.security import hash_password

sqlite_url = 'sqlite:///./src/db/database.sqlite'

engine = create_engine(sqlite_url, echo=True)
with engine.begin() as conn:
  conn.execute(text('PRAGMA foreign_keys=ON'))  # for SQLite only


class TransactionCSVModel(BaseModel):
  date: datetime
  type: str
  actif_a_id: str
  qty_a: float
  actif_v_id: str | None = None
  price: float | None = None
  qty_v: float | None = None
  destination: str
  origin: str | None = None
  actif_f_id: str | None = None
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
    username='laure',
    email='flammecup1992@hotmail.com',
    hashed_password=hash_password('Jtmbmu6-'),
  )
  user4 = User(
    username='test',
    email='test@hotmail.com',
    hashed_password=hash_password('Jtmbmu6-'),
  )

  with Session(engine) as session:
    session.exec(delete(User))  # type: ignore

    session.add(user1)
    session.add(user2)
    session.add(user3)
    session.add(user4)

    session.commit()


def resetTokens():
  with Session(engine) as session:
    # session.exec(delete(Token))

    session.merge(Token(cg_id='fiat_eur', symbol='EUR', name='Euro', price=1))
    session.merge(Token(cg_id='fiat_usd', symbol='USD', name='Dollar US', price=1))
    session.merge(Token(cg_id='fiat_cad', symbol='CAD', name='Dollar CA', price=1))
    session.merge(Token(cg_id='fiat_chf', symbol='CHF', name='Franc suisse', price=1))
    session.commit()


def resetTransactions():
  with open('./src/transactions.csv', 'rt', encoding='utf-8', newline='') as f:
    reader = csv.reader(f)
    headers = next(reader)
    rows = list(reader)
  transactions = [convert_transaction(dict(zip(headers, row))) for row in rows]

  with Session(engine) as session:
    fkaisin_uid = session.exec(select(User.uid).where(User.username == 'fkaisin')).one()
    session.exec(delete(Transaction))  # type: ignore

    for trx in transactions:
      a = session.get(Token, trx['actif_a_id'])
      if not a:
        print('actif manquant dans Token :', trx['actif_a_id'])
        return

      trx['user_id'] = fkaisin_uid
      session.add(Transaction(**trx))
    session.commit()


def assign_transactions_to_ariane():
  with Session(engine) as session:
    user_fk = session.exec(select(User).where(User.username == 'fkaisin')).one()
    user_ak = session.exec(select(User).where(User.username == 'ariane')).one()
    statement = select(Transaction).where(Transaction.user_id == user_fk.uid).limit(5)
    results = session.exec(statement).all()
    for r in results:
      r.user = user_ak
      session.add(r)
    session.commit()
    for r in results:
      session.refresh(r)


def reset_small_tokens():
  small_token_list = ['swarm-markets', 'revest-finance', 'atlas-navi', 'htx-dao']

  with Session(engine) as session:
    session.exec(delete(SmallToken))  # type: ignore
    for st in small_token_list:
      small_tok = SmallToken(id=st)
      session.add(small_tok)
    session.commit()


def setAsset():
  with Session(engine) as session:
    results = session.exec(select(User.uid).where(User.username == 'fkaisin'))
    user_uid = results.one()
    a = Asset(token_id='bitcoin', user_id=user_uid)
    session.add(a)
    session.commit()


if __name__ == '__main__':
  # resetUsers()
  resetTokens()
  # reset_small_tokens()
  # resetTransactions()
  # setAsset()
  # assign_transactions_to_ariane()
