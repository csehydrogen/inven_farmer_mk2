from db import init_db
from dash import Dash, html, dash_table, callback, Input, Output, dcc
import plotly.express as px
from flask import g

def serve_layout():
  con, cur = init_db()
  cur.execute('SELECT * FROM exp_log ORDER BY created_at DESC LIMIT 100')
  data = cur.fetchall()
  fig = px.line(data, x='created_at', y='exp', labels={'created_at': 'Time', 'exp': 'Exp'},
    hover_data={'exp': ':d'})

  return html.Div(children=[
    html.H1(children='Inven Farmer 2.0'),
    html.H2(children='Exp. Graph'),
    dcc.Graph(figure=fig),
    html.H2(children='Exp. from Ad'),
    dash_table.DataTable(
      id='ad_log_table',
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
      style_cell={'textAlign': 'left'},
    ),
    html.H2(children='Misc. log'),
    dash_table.DataTable(
      id='etc_log_table',
      page_current=0,
      page_size=10,
      page_action='custom',
      columns=[
        {'name': 'ID', 'id': 'id'},
        {'name': 'Time', 'id': 'created_at'},
        {'name': 'Type', 'id': 'type'},
        {'name': 'Msg', 'id': 'msg'},
      ],
      style_table={'overflowX': 'scroll'},
      style_cell={'textAlign': 'left'},
    ),
  ])

@callback(
  Output('ad_log_table', 'data'),
  Input('ad_log_table', 'page_current'),
  Input('ad_log_table', 'page_size'))
def update_ad_log_table(page_current, page_size):
  con, cur = init_db()
  cur.execute('SELECT * FROM ad_log ORDER BY created_at DESC LIMIT ? OFFSET ?', (page_size, page_current * page_size))
  data = cur.fetchall()
  return data

@callback(
  Output('etc_log_table', 'data'),
  Input('etc_log_table', 'page_current'),
  Input('etc_log_table', 'page_size'))
def update_etc_log_table(page_current, page_size):
  con, cur = init_db()
  cur.execute('SELECT * FROM etc_log ORDER BY created_at DESC LIMIT ? OFFSET ?', (page_size, page_current * page_size))
  data = cur.fetchall()
  return data

app = Dash()
app.layout = serve_layout

if __name__ == "__main__":
  app.run(host='0.0.0.0', port=22546)
  #app.run(host='0.0.0.0', port=22546, debug=True)