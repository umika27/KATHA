import json,os,uuid
from pathlib import Path
import requests
from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

cfg={"BACKEND_URL":"http://localhost:8000","DEFAULT_LANGUAGE":"hi-en","SCREEN_WIDTH":480,"SCREEN_HEIGHT":320}
p=Path(os.getenv("KATHA_ACCESS_CONFIG","config.json"));cfg.update(json.loads(p.read_text()) if p.exists() else {})
Config.set("graphics","width",str(cfg["SCREEN_WIDTH"]));Config.set("graphics","height",str(cfg["SCREEN_HEIGHT"]))
class KathaApp(App):
 def build(self):
  self.session=os.getenv("KATHA_SESSION_ID","demo-01");self.root=BoxLayout(orientation="vertical",padding=24,spacing=12)
  self.title_label=Label(text="KATHA",font_size="34sp");self.message=Label(text="Tap to speak",font_size="25sp")
  self.lang=Spinner(text=cfg["DEFAULT_LANGUAGE"],values=("hi-en","te-en","bn-en"),size_hint_y=None,height=52)
  self.text=TextInput(text="Scholarship ke liye apply karna hai",multiline=False,size_hint_y=None,height=52)
  self.go=Button(text="Tap to speak / Send mock text",font_size="19sp",size_hint_y=None,height=70,on_press=self.start)
  for w in (self.title_label,self.message,self.lang,self.text,self.go):self.root.add_widget(w)
  return self.root
 def start(self,*_): self.message.text="Listening…";Clock.schedule_once(self.process,.35)
 def process(self,*_): self.message.text="Understanding…";Clock.schedule_once(self.send,.1)
 def send(self,*_):
  try:
   r=requests.post(cfg["BACKEND_URL"]+"/api/access-point/interact",json={"session_id":self.session,"language":self.lang.text,"text":self.text.text},timeout=10);r.raise_for_status();d=r.json()
   self.message.text="✓ Ready" if d["ui_state"]=="READY" else f'{d["missing"] + d["uncertain"] + d["conflicts"]} things still needed\n{d.get("next_question") or ""}'
  except requests.RequestException:self.message.text="Could not connect\nTry again"
if __name__=="__main__":KathaApp().run()
