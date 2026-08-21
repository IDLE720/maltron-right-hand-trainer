"""Right Hand Quest live-key overlay for macOS.

Requires pynput. macOS will ask for Accessibility and Input Monitoring permission.
The overlay never blocks input and keeps typed preview text only in memory.
"""
from __future__ import annotations
import json, os, queue, sys, tkinter as tk, webbrowser
from pathlib import Path
from pynput import keyboard, mouse

APP_DIR=Path.home()/"Library"/"Application Support"/"RightHandQuest"
SETTINGS=APP_DIR/"overlay-macos.json"
COLORS={"bg":"#102f27","panel":"#173a31","key":"#294c43","edge":"#41675c","text":"#f7f8f1","muted":"#91aaa2","lime":"#c9f43f","ink":"#14231f","index":"#55b8d5","middle":"#62c85d","ring":"#efd44b","little":"#ef654e","thumb":"#d84cac"}
HOME=set("ATEH"); FINGERS=["index","index","middle","ring","little","little"]

def asset(name): return Path(getattr(sys,"_MEIPASS",Path(__file__).resolve().parent))/"assets"/name

def load_settings():
    try:return json.loads(SETTINGS.read_text())
    except Exception:return {}

class MacOverlay:
    def __init__(self):
        self.settings=load_settings(); self.opacity=float(self.settings.get("opacity",.82)); self.follow=True
        self.events=queue.Queue(); self.keys={}; self.fade_jobs={}; self.history=[]; self.text=""; self.held=set(); self.clear_job=None
        self.last_click=None; self.last_typing_anchor=None
        self.root=tk.Tk(); self.root.title("Right Hand Quest — Live Keys"); self.root.configure(bg=COLORS["bg"])
        self.root.attributes("-topmost",True,"-alpha",self.opacity); self.root.resizable(False,False)
        try:self.icon=tk.PhotoImage(file=str(asset("right-hand-quest.png")));self.root.iconphoto(True,self.icon)
        except Exception:pass
        self.build(); self.place(); self.start_listeners(); self.root.after(15,self.drain); self.root.protocol("WM_DELETE_WINDOW",self.close)

    def build(self):
        head=tk.Frame(self.root,bg=COLORS["bg"],height=40,cursor="fleur",highlightbackground=COLORS["edge"],highlightthickness=1);head.pack(fill="x");head.pack_propagate(False)
        tk.Label(head,text="●  LIVE KEYS  macOS",fg=COLORS["lime"],bg=COLORS["bg"],font=("Menlo",9,"bold")).pack(side="left",padx=10)
        self.button(head,"×",self.close);self.button(head,"−",self.minimize)
        self.opacity_btn=self.button(head,f"{round(self.opacity*100)}%",self.cycle_opacity,5)
        self.button(head,"▶",lambda:webbrowser.open("https://idle720.github.io/maltron-right-hand-trainer/"))
        self.follow_btn=self.button(head,"⌖",self.toggle_follow);self.update_follow()
        for w in (head,):w.bind("<ButtonPress-1>",self.drag_start);w.bind("<B1-Motion>",self.drag_move);w.bind("<ButtonRelease-1>",lambda e:self.save())
        self.body=tk.Frame(self.root,bg=COLORS["panel"],padx=12,pady=10,highlightbackground=COLORS["edge"],highlightthickness=1);self.body.pack()
        read=tk.Frame(self.body,bg=COLORS["panel"]);read.pack(fill="x",pady=(0,8))
        self.history_label=tk.Label(read,text="Waiting for a key…",fg=COLORS["text"],bg=COLORS["panel"],font=("Menlo",8),width=35,anchor="w");self.history_label.pack(side="left")
        self.current=tk.Label(read,text="—",fg=COLORS["lime"],bg=COLORS["panel"],font=("Helvetica",19,"bold"),width=9,anchor="e");self.current.pack(side="right")
        typed=tk.Frame(self.body,bg=COLORS["bg"],padx=8,pady=6,highlightbackground=COLORS["edge"],highlightthickness=1);typed.pack(fill="x",pady=(0,10))
        tk.Label(typed,text="TYPED TEXT",fg=COLORS["muted"],bg=COLORS["bg"],font=("Menlo",7)).pack(anchor="w")
        self.preview=tk.Text(typed,fg=COLORS["text"],bg=COLORS["bg"],font=("Menlo",10),width=62,height=3,wrap="word",bd=0,takefocus=False);self.preview.pack();self.set_preview("Your typing will appear here…")
        board=tk.Frame(self.body,bg=COLORS["panel"]);board.pack();thumb=tk.Frame(board,bg=COLORS["panel"]);thumb.grid(row=0,column=0,sticky="se",padx=(0,4));letters=tk.Frame(board,bg=COLORS["panel"]);letters.grid(row=0,column=1)
        for r,row in enumerate(["XGMPBQ","JFDOLR","SATEHN","ZYCKWV"]):
            for c,ch in enumerate(row):self.make_key(letters,ch,r,c,FINGERS[c],ch in HOME)
        self.make_key(thumb,"BACKSPACE",2,3,"thumb",width=8);self.make_key(thumb,"ENTER",3,2,"thumb",width=7);self.make_key(thumb,"I",3,3,"thumb");self.make_key(thumb,"SHIFT",4,1,"thumb",width=7);self.make_key(thumb,"U",4,2,"thumb")
        space=self.make_key(thumb,"SPACE",4,3,"thumb",True,width=8);space.grid(row=4,column=3,rowspan=2,sticky="nsew",padx=2,pady=2)
        self.make_key(thumb,",",5,1,"thumb");self.make_key(thumb,".",5,2,"thumb")
        tk.Label(self.body,text="▶ training • ⌖ follow typing",fg=COLORS["muted"],bg=COLORS["panel"],font=("Menlo",7)).pack(pady=(8,0))

    def button(self,parent,text,cmd,width=3):
        b=tk.Button(parent,text=text,command=cmd,fg=COLORS["text"],bg=COLORS["bg"],activebackground=COLORS["edge"],bd=0,width=width);b.pack(side="right",fill="y");return b
    def make_key(self,parent,ch,r,c,finger,home=False,width=5):
        outer=tk.Frame(parent,bg=COLORS[finger],padx=1,pady=1);outer.grid(row=r,column=c,padx=2,pady=2,sticky="nsew")
        label=tk.Label(outer,text=ch,width=width,bg="#365746" if home else COLORS["key"],fg=COLORS["text"],font=("Menlo",10,"bold"),pady=6);label.pack(fill="both",expand=True);self.keys[ch]=label;return outer
    def place(self):
        self.root.update_idletasks();x=int(self.settings.get("x",self.root.winfo_screenwidth()-self.root.winfo_reqwidth()-20));y=int(self.settings.get("y",self.root.winfo_screenheight()-self.root.winfo_reqheight()-60));self.root.geometry(f"+{max(0,x)}+{max(0,y)}")
    def save(self):
        APP_DIR.mkdir(parents=True,exist_ok=True);SETTINGS.write_text(json.dumps({"x":self.root.winfo_x(),"y":self.root.winfo_y(),"opacity":self.opacity,"follow":self.follow}))
    def drag_start(self,e):self.drag=(e.x_root-self.root.winfo_x(),e.y_root-self.root.winfo_y())
    def drag_move(self,e):self.root.geometry(f"+{e.x_root-self.drag[0]}+{e.y_root-self.drag[1]}")
    def minimize(self):self.root.iconify()
    def toggle_follow(self):self.follow=not self.follow;self.update_follow();self.save()
    def update_follow(self):self.follow_btn.config(text="⌖" if self.follow else "○",fg=COLORS["lime"] if self.follow else COLORS["muted"])
    def cycle_opacity(self):
        levels=(.82,.65,1.0);i=min(range(3),key=lambda n:abs(levels[n]-self.opacity));self.opacity=levels[(i+1)%3];self.root.attributes("-alpha",self.opacity);self.opacity_btn.config(text=f"{round(self.opacity*100)}%");self.save()
    def set_preview(self,text):self.preview.config(state="normal");self.preview.delete("1.0","end");self.preview.insert("1.0",text);self.preview.see("end");self.preview.config(state="disabled")

    @staticmethod
    def label(key):
        if isinstance(key,keyboard.KeyCode):return key.char.upper() if key.char else None
        return {keyboard.Key.space:"SPACE",keyboard.Key.enter:"ENTER",keyboard.Key.backspace:"BACKSPACE",keyboard.Key.shift:"SHIFT",keyboard.Key.shift_r:"SHIFT",keyboard.Key.tab:"TAB",keyboard.Key.ctrl:"CTRL",keyboard.Key.ctrl_r:"CTRL",keyboard.Key.alt:"ALT",keyboard.Key.alt_r:"ALT",keyboard.Key.caps_lock:"CAPS"}.get(key)
    def start_listeners(self):
        self.kl=keyboard.Listener(on_press=lambda k:self.events.put(("key",self.label(k),True)),on_release=lambda k:self.events.put(("key",self.label(k),False)));self.kl.start()
        self.ml=mouse.Listener(on_click=lambda x,y,b,pressed:self.events.put(("click",x,y)) if b==mouse.Button.left and not pressed else None);self.ml.start()
    def drain(self):
        try:
            while True:
                event=self.events.get_nowait()
                if event[0]=="click":self.remember_click(event[1],event[2])
                elif event[1]:self.key_event(event[1],event[2])
        except queue.Empty:pass
        self.root.after(15,self.drain)
    def remember_click(self,x,y):
        # A click becomes a candidate location; the overlay only moves once a
        # real typing key confirms that text entry is happening there.
        if self.root.winfo_x()<=x<=self.root.winfo_x()+self.root.winfo_width() and self.root.winfo_y()<=y<=self.root.winfo_y()+self.root.winfo_height():return
        self.last_click=(x,y);self.last_typing_anchor=None
    def follow_typing(self):
        if not self.follow or not self.last_click or self.last_click==self.last_typing_anchor:return
        x,y=self.last_click;self.last_typing_anchor=self.last_click
        self.root.update_idletasks();w,h=self.root.winfo_width(),self.root.winfo_height();sw,sh=self.root.winfo_screenwidth(),self.root.winfo_screenheight();nx=x+20 if x+20+w<sw else x-w-20;ny=y+20 if y+20+h<sh else y-h-20;self.root.geometry(f"+{max(0,int(nx))}+{max(0,int(ny))}");self.root.lift();self.save()
    def key_event(self,label,down):
        if down:
            if label not in ("SHIFT","CTRL","ALT","CAPS"):self.follow_typing()
            if label in ("SHIFT","CTRL","ALT"):self.held.add(label)
            self.current.config(text=label);self.history.append(label);self.history=self.history[-6:];self.history_label.config(text=" · ".join(self.history));self.update_text(label)
            if self.clear_job:self.root.after_cancel(self.clear_job)
            self.clear_job=self.root.after(60000,self.clear_text)
        elif label in ("SHIFT","CTRL","ALT"):self.held.discard(label)
        if label in self.keys:
            if down:self.keys[label].config(bg=COLORS["lime"],fg=COLORS["ink"])
            else:self.fade(label)
    def update_text(self,label):
        if label=="BACKSPACE":self.text=self.text[:-1]
        elif label=="SPACE":self.text+=" "
        elif label=="ENTER":self.text+="\n"
        elif label in (",","."):self.text+=label
        elif len(label)==1 and label.isalnum() and not ({"CTRL","ALT"}&self.held):self.text+=label if "SHIFT" in self.held else label.lower()
        self.text=self.text[-2000:];self.set_preview(self.text or "Your typing will appear here…")
    def fade(self,label):
        key=self.keys[label];rest="#365746" if label in HOME or label=="SPACE" else COLORS["key"]
        def step(n=1):
            def blend(a,b,t):
                x=[int(a[i:i+2],16) for i in (1,3,5)];y=[int(b[i:i+2],16) for i in (1,3,5)];return "#"+"".join(f"{round(p+(q-p)*t):02x}" for p,q in zip(x,y))
            key.config(bg=blend(COLORS["lime"],rest,n/12),fg=blend(COLORS["ink"],COLORS["text"],n/12))
            if n<12:self.root.after(90,step,n+1)
        self.root.after(260,step)
    def clear_text(self):self.text="";self.clear_job=None;self.set_preview("")
    def close(self):
        self.save();self.kl.stop();self.ml.stop();self.root.destroy()
    def run(self):self.root.mainloop()

if __name__=="__main__":MacOverlay().run()
