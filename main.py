from lxml import etree
import random
import re
import requests
from requests import Session
from requests import adapters
from urllib3 import poolmanager
from ssl import create_default_context, Purpose, CERT_NONE
import urllib3
import sqlite3
import traceback
from dash import Dash, html, dash_table, callback, Input, Output, dcc
import plotly.graph_objs as go
import multiprocessing
import plotly.express as px
from dotenv import dotenv_values

CONFIG = dotenv_values(".env")
AD_SEARCH_RE_ENG = re.compile('^.*["\'](.*zicf\\.inven\\.co\\.kr.*)["\'].*$', re.MULTILINE)

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def init_db():
  con = sqlite3.connect('inven_farmer.db', check_same_thread=False)
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
  cur.execute('''CREATE TABLE IF NOT EXISTS err_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )''')
  con.commit()
  return con, cur

con, cur = init_db()

# To avoid "unsafe legacy renegotiation disabled" error; https://gist.github.com/FluffyDietEngine/94c0137445555a418ac9f332edfa6f4b
# Also use verify=False; e.g., requests.get(..., verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CustomHttpAdapter (adapters.HTTPAdapter):
    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = poolmanager.PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_context=self.ssl_context)

def ssl_supressed_session():
    ctx = create_default_context(Purpose.SERVER_AUTH)
    # to bypass verification after accepting Legacy connections
    ctx.check_hostname = False
    ctx.verify_mode = CERT_NONE
    # accepting legacy connections
    ctx.options |= 0x4    
    session = Session()
    session.mount('https://', CustomHttpAdapter(ctx))
    return session

def encode_password(pw):
  return ''.join([f'{ord(c):02x}' for c in pw])

def login(sess):
  pw = encode_password(CONFIG['INVEN_PW'])
  res = sess.post("https://member.inven.co.kr/m/login/dispatch", data={
    "user_id": CONFIG['INVEN_ID'],
    "password": pw,
  })

def get_exp(sess):
  res = sess.get("https://www.inven.co.kr/member/skill/")
  tree = etree.HTML(res.text)
  cands = tree.xpath('//dt[text()="경험치"]/following-sibling::dd')
  exp = int(cands[0].text.replace(',', ''))
  return exp

def get_ad(sess, con, cur):
  inven_list = ["2631bbs", "asusrog", "gfn", "intel", "it", "msi", "r2", "webzine", "zotac"]
  device_list = ["inven", "minven"]
  brand_list = ["samsungodyssey", "intel", "asusrog", "hyperx", "msi", "legion", "omen", "logitech", "steelseries", "klevv", "secretlab", "turtlebeach", "roccat", "sidizgaming", "ultimater"]

  inven = random.choice(inven_list)
  device = random.choice(device_list)
  url = 'https://zicf.inven.co.kr/RealMedia/ads/adstream_sx.ads/' + device + '/' + inven
  res = sess.get(url)
  items = AD_SEARCH_RE_ENG.findall(res.text)
  if len(items) == 0:
    print(res.text)
    print(f"No ad found in {url} ^^^")
    return

  adurl = items[0]
  if adurl.startswith('//'):
    adurl = 'https:' + adurl
  print(f'Found ad: {adurl} in {url}')
  pre_exp = get_exp(sess)
  try:
    sess.get(adurl, timeout=10, verify=False)
  except requests.exceptions.ReadTimeout:
    print(f'Timeout on {adurl}')
    return
  post_exp = get_exp(sess)
  print(f'Exp: {pre_exp} -> {post_exp}')
  if pre_exp < post_exp:
    cur.execute('INSERT INTO ad_log (ad_url, src_url, exp_gain) VALUES (?, ?, ?)', (adurl, url, post_exp - pre_exp))
    cur.execute('INSERT INTO exp_log (exp) VALUES (?)', (post_exp,))
    con.commit()

def main():
  sess = ssl_supressed_session()
  login(sess)
  while True:
    try:
      get_ad(sess, con, cur)
    except KeyboardInterrupt:
      print('^C received, shutting down')
      break
    except:
      err_str = traceback.format_exc()
      print(err_str)
      cur.execute('INSERT INTO err_log (msg) VALUES (?)', (err_str,))
      con.commit()

# https://dash.plotly.com/live-updates
app = Dash()
def serve_layout():
  #cur.execute('SELECT * FROM ad_log ORDER BY created_at DESC LIMIT 10')
  #data = cur.fetchall()
  cur.execute('SELECT * FROM exp_log ORDER BY created_at DESC LIMIT 100')
  data = cur.fetchall()
  fig = px.line(data, x='created_at', y='exp', labels={'created_at': 'Time', 'exp': 'Exp'})

  return html.Div(children=[
    html.H1(children='Inven Farmer 2.0'),
    html.H2(children='Exp. Graph'),
    dcc.Graph(figure=fig),
    html.H2(children='Exp. from Ad'),
    dash_table.DataTable(
      id='ad_log_table',
      #data=data,
      page_current=0,
      page_size=10,
      page_action='custom',
      columns=[
        {'name': 'ID', 'id': 'id'},
        {'name': 'Time', 'id': 'created_at'},
        {'name': 'Exp Gain', 'id': 'exp_gain'},
        {'name': 'Ad URL', 'id': 'ad_url'},
        {'name': 'Src URL', 'id': 'src_url'},
      ],
      style_table={'overflowX': 'scroll'},
    ),
  ])
app.layout = serve_layout
@callback(
  Output('ad_log_table', 'data'),
  Input('ad_log_table', 'page_current'),
  Input('ad_log_table', 'page_size'))
def update_table(page_current, page_size):
  cur.execute('SELECT * FROM ad_log ORDER BY created_at DESC LIMIT ? OFFSET ?', (page_size, page_current * page_size))
  data = cur.fetchall()
  return data


if __name__ == "__main__":
  p = multiprocessing.Process(target=main)
  p.start()
  app.run(debug=True, host='0.0.0.0', port=22546)
  p.terminate()