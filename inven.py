from db import init_db
from dotenv import dotenv_values
import re
import urllib3
from requests import Session
from requests import adapters
from urllib3 import poolmanager
from ssl import create_default_context, Purpose, CERT_NONE
from lxml import etree
import random
import requests
import traceback
import json
from datetime import datetime
import time

CONFIG = dotenv_values(".env")
AD_SEARCH_RE_ENG = re.compile('^.*["\'](.*zicf\\.inven\\.co\\.kr.*)["\'].*$', re.MULTILINE)

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

def get_fire(sess, con, cur):
  res = sess.post("https://member.inven.co.kr/user/scorpio/chk/skill/point",
    headers={'referer': 'https://member.inven.co.kr/user/scorpio/mlogin'},
    data={
      "surl": "https://www.inven.co.kr/"
    }
  )
  resj = json.loads(res.text)
  if resj['result'] != 'success' or resj['login'] == None:
    raise Exception(f'Failed to get fire: {res.text}')
  cur.execute('INSERT INTO etc_log (type, msg) VALUES (?, ?)', ('fire', res.text))
  con.commit()

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
    raise Exception(f"No ad found in {url}")

  adurl = items[0]
  if adurl.startswith('//'):
    adurl = 'https:' + adurl
  pre_exp = get_exp(sess)
  try:
    sess.get(adurl, timeout=10, verify=False)
  except requests.exceptions.ReadTimeout:
    raise Exception(f'ReadTimeout on {adurl}')
  except requests.exceptions.ConnectionError:
    raise Exception(f'ConnectionError on {adurl}')
  post_exp = get_exp(sess)
  print(f'Exp: {pre_exp} -> {post_exp}, visited {adurl}')
  if pre_exp < post_exp:
    cur.execute('INSERT INTO ad_log (ad_url, src_url, exp_gain) VALUES (?, ?, ?)', (adurl, url, post_exp - pre_exp))
    cur.execute('INSERT INTO exp_log (exp) VALUES (?)', (post_exp,))
    con.commit()

def get_imarble(sess, con, cur):
  res = sess.post("https://imart.inven.co.kr/imarble/index.php", data={
    'mode': 'playGame',
  })
  result = json.loads(res.text)['result']
  if result != 'success':
    raise Exception(f'Failed to play imarble: {res.text}')
  cur.execute('INSERT INTO etc_log (type, msg) VALUES (?, ?)', ('imarble', res.text))
  con.commit()

def get_attend(sess, con, cur):
  yyyymm = datetime.today().strftime('%Y%m')
  res = sess.post("https://imart.inven.co.kr/attendance/attend_apply.ajax.php",
    headers={'referer': 'https://imart.inven.co.kr/attendance/'},
    data={'attendCode': yyyymm})
  if 'success' not in res.text:
    raise Exception(f'Failed to register attend: {res.text}')
  cur.execute('INSERT INTO etc_log (type, msg) VALUES (?, ?)', ('attend', res.text))
  con.commit()

def inven_main():
  con, cur = init_db()
  sess = ssl_supressed_session()
  login(sess)

  it = 0
  while True:
    try:
      if it % 2000 == 0:
        get_fire(sess, con, cur)
        time.sleep(1)
        get_attend(sess, con, cur)
        time.sleep(1)
        for i in range(6):
          get_imarble(sess, con, cur)
          time.sleep(1)
      get_ad(sess, con, cur)
      time.sleep(1)
    except KeyboardInterrupt:
      print('^C received, shutting down')
      break
    except:
      err_str = traceback.format_exc()
      cur.execute('INSERT INTO etc_log (type, msg) VALUES (?, ?)', ('error', err_str))
      con.commit()
    it += 1
  
if __name__ == "__main__":
  inven_main()