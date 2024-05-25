import sqlite3

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def init_db():
  #con = sqlite3.connect('inven_farmer.db', check_same_thread=False)
  con = sqlite3.connect('inven_farmer.db')
  con.row_factory = dict_factory
  cur = con.cursor()
  cur.execute('''CREATE TABLE IF NOT EXISTS ad_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_url TEXT NOT NULL,
    src_url TEXT NOT NULL,
    exp_gain INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )''')
  cur.execute('''CREATE TABLE IF NOT EXISTS exp_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exp INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )''')
  cur.execute('''CREATE TABLE IF NOT EXISTS etc_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    msg TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )''')
  con.commit()
  return con, cur