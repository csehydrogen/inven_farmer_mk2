import multiprocessing
from webapp import app
from inven import inven_main

if __name__ == "__main__":
  p = multiprocessing.Process(target=inven_main)
  p.start()
  app.run(host='0.0.0.0', port=22546)
  #app.run(host='0.0.0.0', port=22546, debug=True)
  p.terminate()