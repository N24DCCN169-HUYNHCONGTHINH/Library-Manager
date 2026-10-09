
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
import hashlib
import unicodedata
try:
    from PIL import Image, ImageTk, ImageOps, ImageDraw
    PIL_OK = True
except ImportError:
    PIL_OK = False
from datetime import datetime, timedelta
from pathlib import Path
import calendar
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "library_manager.db")
COVER_DIR = os.path.join(BASE_DIR, "covers")
os.makedirs(COVER_DIR, exist_ok=True)
FINE_PER_DAY = 5000

def hash_pw(pw):
    """Bam mat khau bang SHA-256 truoc khi luu/so sanh trong DB (khong luu plaintext)."""
    return hashlib.sha256((pw or "").encode("utf-8")).hexdigest()

def strip_accents(text):
    """Bo dau tieng Viet de tim kiem khong phan biet dau (vd: 'co ban' van tim ra 'Cơ Bản')."""
    t=unicodedata.normalize("NFD",str(text or "")).replace("đ","d").replace("Đ","D")
    return "".join(ch for ch in t if unicodedata.category(ch)!="Mn")

def pdf_fonts():
    """Dang ky font Unicode de PDF hien thi dung tieng Viet co dau. Tra ve (font thuong, font dam)."""
    if not REPORTLAB_OK: return "Helvetica","Helvetica-Bold"
    pairs=[("C:/Windows/Fonts/arial.ttf","C:/Windows/Fonts/arialbd.ttf"),
           ("/Library/Fonts/Arial.ttf","/Library/Fonts/Arial Bold.ttf"),
           ("/System/Library/Fonts/Supplemental/Arial.ttf","/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
           ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf","/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
    for reg,bold in pairs:
        if os.path.exists(reg) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont("VN-Regular",reg)); pdfmetrics.registerFont(TTFont("VN-Bold",bold))
                return "VN-Regular","VN-Bold"
            except Exception: pass
    return "Helvetica","Helvetica-Bold"

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB)
        self.conn.create_function("unaccent",1,strip_accents)
        self.create()

    def create(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE, password TEXT, role TEXT,
            status TEXT DEFAULT 'Active')""")
        c.execute("""CREATE TABLE IF NOT EXISTS books(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE, title TEXT, author TEXT,
            category TEXT, publisher TEXT, year INTEGER,
            quantity INTEGER, available INTEGER, cover TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS readers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE, name TEXT, phone TEXT, address TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS borrowings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER, reader_id INTEGER,
            borrow_date TEXT, due_date TEXT, return_date TEXT,
            fine INTEGER DEFAULT 0, status TEXT)""")
        self.conn.commit()
        self.seed()

    def seed(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                      ("admin",hash_pw("123456"),"Admin"))
            c.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                      ("librarian",hash_pw("123456"),"Librarian"))
        c.execute("SELECT COUNT(*) FROM books")
        if c.fetchone()[0] == 0:
            books = [
                ("BK001","Python Cơ Bản","Nguyễn Văn A","CNTT","NXB Trẻ",2024,5,5,""),
                ("BK002","Lập Trình C++","Bjarne Stroustrup","CNTT","NXB Giáo Dục",2023,4,4,""),
                ("BK003","Cấu Trúc Dữ Liệu","Mark Allen Weiss","CNTT","NXB Đại Học",2022,3,3,""),
                ("BK004","Cơ Sở Dữ Liệu","Nguyễn Văn B","CNTT","NXB Khoa Học",2024,6,6,""),
                ("BK005","Clean Code","Robert C. Martin","CNTT","Prentice Hall",2020,2,2,"")
            ]
            c.executemany("""INSERT INTO books
                (code,title,author,category,publisher,year,quantity,available,cover)
                VALUES(?,?,?,?,?,?,?,?,?)""", books)
        # Gan anh bia mau cho cac sach demo
        c.execute("UPDATE books SET cover=? WHERE code=? AND (cover IS NULL OR cover='')", (os.path.join(COVER_DIR,"BK001.png"), "BK001"))
        c.execute("UPDATE books SET cover=? WHERE code=? AND (cover IS NULL OR cover='')", (os.path.join(COVER_DIR,"BK002.png"), "BK002"))
        c.execute("UPDATE books SET cover=? WHERE code=? AND (cover IS NULL OR cover='')", (os.path.join(COVER_DIR,"BK003.png"), "BK003"))
        c.execute("UPDATE books SET cover=? WHERE code=? AND (cover IS NULL OR cover='')", (os.path.join(COVER_DIR,"BK004.png"), "BK004"))
        c.execute("UPDATE books SET cover=? WHERE code=? AND (cover IS NULL OR cover='')", (os.path.join(COVER_DIR,"BK005.png"), "BK005"))
        c.execute("SELECT COUNT(*) FROM readers")
        if c.fetchone()[0] == 0:
            readers = [
                ("DG001","Nguyễn Văn An","0900000001","TP HCM"),
                ("DG002","Trần Thị Bình","0900000002","TP HCM"),
                ("DG003","Lê Văn Cường","0900000003","Đồng Nai")]
            c.executemany("INSERT INTO readers(code,name,phone,address) VALUES(?,?,?,?)",
                          readers)
        self.conn.commit()

class LibraryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Library Manager")
        self.root.geometry("1300x760")
        self.root.minsize(1050,650)
        self.db = Database()
        self.user = None
        self.role = None
        self.C = {
            "bg":"#F5F7FA","side":"#FFFFFF","side2":"#EAF7EF",
            "green":"#2E8B57","green2":"#49B66B","dark":"#24313A","muted":"#718096",
            "border":"#D9E2E8","blue":"#3578E5","red":"#D9534F",
            "orange":"#E9A23B"}
        self.style()
        self.root.protocol("WM_DELETE_WINDOW", self.exit)
        self.login()

    def style(self):
        s=ttk.Style()
        try: s.theme_use("clam")
        except: pass
        s.configure("Treeview",rowheight=34,font=("Segoe UI",10),
                    background="white",fieldbackground="white")
        s.configure("Treeview.Heading",font=("Segoe UI",10,"bold"),
                    background="#EAF2EF",foreground=self.C["dark"],padding=8)

    def clear(self, parent=None):
        parent = parent or self.root
        for w in parent.winfo_children(): w.destroy()

    def button(self,p,text,cmd,kind="green",width=15):
        colors={"green":(self.C["green"],"#246B45","white"),
                "blue":(self.C["blue"],"#285FB7","white"),
                "red":(self.C["red"],"#B63D39","white"),
                "gray":("#E8EDF0","#D8E0E5",self.C["dark"]),
                "orange":(self.C["orange"],"#C98A28","white")}
        bg,active,fg=colors[kind]
        return tk.Button(p,text=text,command=cmd,width=width,bg=bg,
                         activebackground=active,fg=fg,activeforeground=fg,
                         relief="flat",bd=0,font=("Segoe UI",10,"bold"),
                         cursor="hand2",pady=7)

    # ---------------- LOGIN ----------------
    def login(self):
        self.clear()
        self.root.configure(bg=self.C["bg"])
        left=tk.Frame(self.root,bg=self.C["side"],width=500)
        left.pack(side="left",fill="y"); left.pack_propagate(False)
        tk.Label(left,text="LIBRARY",bg=self.C["side"],fg="white",
                 font=("Segoe UI",32,"bold")).pack(pady=(150,0))
        tk.Label(left,text="MANAGER",bg=self.C["side"],fg="#8DD5B0",
                 font=("Segoe UI",32,"bold")).pack()
        tk.Label(left,text="Hệ thống quản lý thư viện",
                 bg=self.C["side"],fg="#D7EEE4",
                 font=("Segoe UI",12)).pack(pady=12)
        right=tk.Frame(self.root,bg="white")
        right.pack(side="right",fill="both",expand=True)
        f=tk.Frame(right,bg="white"); f.place(relx=.5,rely=.5,anchor="center")
        tk.Label(f,text="Đăng nhập",bg="white",fg=self.C["dark"],
                 font=("Segoe UI",26,"bold")).pack(anchor="w")
        tk.Label(f,text="Đăng nhập để tiếp tục",bg="white",
                 fg=self.C["muted"]).pack(anchor="w",pady=(4,25))
        tk.Label(f,text="Tên đăng nhập",bg="white",font=("Segoe UI",10,"bold")).pack(anchor="w")
        self.eu=tk.Entry(f,width=40,font=("Segoe UI",11),relief="solid",bd=1)
        self.eu.pack(fill="x",ipady=8,pady=(5,15))
        tk.Label(f,text="Mật khẩu",bg="white",font=("Segoe UI",10,"bold")).pack(anchor="w")
        pw_row=tk.Frame(f,bg="white"); pw_row.pack(fill="x",pady=(5,15))
        self.ep=tk.Entry(pw_row,width=40,show="*",font=("Segoe UI",11),relief="solid",bd=1)
        self.ep.pack(side="left",fill="x",expand=True,ipady=8)
        self.show_pw=False
        def toggle_pw():
            self.show_pw=not self.show_pw
            self.ep.config(show="" if self.show_pw else "*")
            btn_eye.config(text="🙈" if self.show_pw else "👁")
        btn_eye=tk.Button(pw_row,text="👁",command=toggle_pw,width=4,bg="#E8EDF0",
                          activebackground="#D8E0E5",fg=self.C["dark"],relief="flat",
                          font=("Segoe UI Emoji",11),cursor="hand2")
        btn_eye.pack(side="left",fill="y",padx=(6,0))
        self.button(f,"ĐĂNG NHẬP",self.do_login,width=30).pack(fill="x")
        tk.Label(f,text="Demo: admin / 123456",bg="white",fg=self.C["muted"]).pack(pady=15)
        self.eu.focus()
        self.root.bind("<Return>",lambda e:self.do_login())

    def do_login(self):
        c=self.db.conn.cursor()
        uname=self.eu.get().strip(); pw=self.ep.get()
        c.execute("""SELECT username,password,role FROM users
                     WHERE username=? AND status='Active'""",(uname,))
        r=c.fetchone()
        if not r or r[1] not in (hash_pw(pw),pw):
            messagebox.showerror("Đăng nhập","Sai tài khoản hoặc mật khẩu."); return
        if r[1]==pw:
            # Mat khau dang o dang plaintext cu (tu DB truoc khi co hash) -> nang cap len hash
            c.execute("UPDATE users SET password=? WHERE username=?",(hash_pw(pw),r[0]))
            self.db.conn.commit()
        self.user,self.role=r[0],r[2]
        self.root.unbind("<Return>")
        self.main()

    # ---------------- MAIN ----------------
    def main(self):
        self.clear()
        side=tk.Frame(self.root,bg=self.C["side"],width=255,
                      highlightbackground=self.C["border"],highlightthickness=1)
        side.pack(side="left",fill="y"); side.pack_propagate(False)

        # Logo area
        logo=tk.Frame(side,bg="white",height=100)
        logo.pack(fill="x"); logo.pack_propagate(False)
        iconbox=tk.Frame(logo,bg=self.C["green"],width=44,height=44)
        iconbox.place(x=20,y=22); iconbox.pack_propagate(False)
        tk.Label(iconbox,text="▤",bg=self.C["green"],fg="white",
                 font=("Segoe UI Symbol",22,"bold")).place(relx=.5,rely=.5,anchor="center")
        tk.Label(logo,text="LIBRARY",bg="white",fg=self.C["dark"],
                 font=("Segoe UI",16,"bold")).place(x=75,y=22)
        tk.Label(logo,text="MANAGEMENT SYSTEM",bg="white",fg=self.C["green"],
                 font=("Segoe UI",8,"bold")).place(x=76,y=48)

        tk.Frame(side,bg=self.C["border"],height=1).pack(fill="x",padx=18)
        tk.Label(side,text="MENU",bg="white",fg="#9AA7B2",
                 font=("Segoe UI",8,"bold")).pack(anchor="w",padx=22,pady=(18,7))

        groups=[
            ("DỊCH VỤ SÁCH",[("⌂", "Tổng quan",self.dashboard),
                             ("▣", "Tìm sách",self.books),
                             ("＋", "Thêm sách",self.add_book)]),
            ("MƯỢN / TRẢ",[("↔", "Mượn sách",self.borrow),
                            ("✓", "Trả sách",self.returns),
                            ("▤", "Phiếu mượn",self.loans),
                            ("!", "Sách quá hạn",self.overdue)]),
            ("QUẢN LÝ",[("♙", "Độc giả",self.readers),
                         ("▥", "Báo cáo",self.report)])]
        for g,items in groups:
            tk.Label(side,text=g,bg="white",fg="#9AA7B2",
                     font=("Segoe UI",8,"bold")).pack(anchor="w",padx=22,pady=(13,5))
            for ico,text,cmd in items:
                self.menu(side,ico,text,cmd)
        if self.role=="Admin":
            tk.Label(side,text="HỆ THỐNG",bg="white",fg="#9AA7B2",
                     font=("Segoe UI",8,"bold")).pack(anchor="w",padx=22,pady=(13,5))
            self.menu(side,"⚙","Tài khoản",self.users)

        # User card at bottom
        usercard=tk.Frame(side,bg="#F4FAF6",highlightbackground="#DCEDE2",highlightthickness=1)
        usercard.pack(side="bottom",fill="x",padx=14,pady=14)
        avatar=tk.Frame(usercard,bg=self.C["green"],width=34,height=34)
        avatar.pack(side="left",padx=10,pady=10); avatar.pack_propagate(False)
        tk.Label(avatar,text=self.user[:1].upper(),bg=self.C["green"],fg="white",
                 font=("Segoe UI",11,"bold")).place(relx=.5,rely=.5,anchor="center")
        ui=tk.Frame(usercard,bg="#F4FAF6"); ui.pack(side="left",pady=8)
        tk.Label(ui,text=self.user,bg="#F4FAF6",fg=self.C["dark"],
                 font=("Segoe UI",9,"bold")).pack(anchor="w")
        tk.Label(ui,text=self.role,bg="#F4FAF6",fg=self.C["muted"],
                 font=("Segoe UI",8)).pack(anchor="w")
        tk.Button(usercard,text="↪",command=self.logout,bg="#F4FAF6",fg=self.C["red"],
                  bd=0,font=("Segoe UI Symbol",14,"bold"),cursor="hand2").pack(side="right",padx=8)

        area=tk.Frame(self.root,bg=self.C["bg"]); area.pack(side="right",fill="both",expand=True)
        top=tk.Frame(area,bg="white",height=68); top.pack(fill="x"); top.pack_propagate(False)
        # Goi cac widget ben trai/phai truoc de "chiem cho" cua chung,
        # sau do khung giua se tu dong lay phan khong gian con lai
        # -> tranh o tim kiem de len tieu de khi tieu de dai hoac cua so hep.
        left=tk.Frame(top,bg="white"); left.pack(side="left")
        tk.Label(left,text="Hệ thống quản lý thư viện",bg="white",fg=self.C["dark"],
                 font=("Segoe UI",13,"bold")).pack(padx=25)
        right=tk.Frame(top,bg="white"); right.pack(side="right")
        self.button(right,"Logout",self.logout,"green",9).pack(side="right",padx=5)
        tk.Label(right,text="♟  "+self.user,bg="white",fg=self.C["dark"],
                 font=("Segoe UI",10,"bold")).pack(side="right",padx=(5,20))
        center=tk.Frame(top,bg="white"); center.pack(side="left",fill="both",expand=True)
        searchbox=tk.Frame(center,bg="#F5F7F8",highlightbackground="#D8E0E5",highlightthickness=1)
        searchbox.place(relx=.5,rely=.5,anchor="center",width=370,height=36)
        tk.Label(searchbox,text="⌕",bg="#F5F7F8",fg=self.C["muted"],
                 font=("Segoe UI Symbol",15)).pack(side="left",padx=8)
        self.quick=tk.Entry(searchbox,width=35,bg="#F5F7F8",fg=self.C["muted"],
                            relief="flat",font=("Segoe UI",9))
        self.quick.pack(side="left",fill="both",expand=True,pady=5)
        self.quick.insert(0,"Tìm kiếm chức năng...")
        self.quick_items=[("Tổng quan",self.dashboard),
                          ("Tìm sách",self.books),
                          ("Thêm sách",self.add_book),
                          ("Mượn sách",self.borrow),
                          ("Trả sách",self.returns),
                          ("Phiếu mượn",self.loans),
                          ("Sách quá hạn",self.overdue),
                          ("Độc giả",self.readers),
                          ("Báo cáo",self.report)]
        if self.role=="Admin":
            self.quick_items.append(("Tài khoản",self.users))
        self._quick_matches=[]
        # Dropdown dat trong "area" (khong phai "top") de khong bi cat boi
        # chieu cao co dinh 68px cua thanh top; y=68 la vua duoi thanh top.
        self.quick_drop=tk.Listbox(area,font=("Segoe UI",10),bd=1,relief="solid",
                                   highlightthickness=0,activestyle="none",
                                   selectbackground=self.C["green"],selectforeground="white")
        def qfocus_in(e):
            if self.quick.get()=="Tìm kiếm chức năng...":
                self.quick.delete(0,"end"); self.quick.config(fg=self.C["dark"])
        def qhide_drop():
            self.quick_drop.place_forget()
        def qfocus_out(e):
            def maybe_hide():
                foc=self.root.focus_get()
                if foc not in (self.quick,self.quick_drop):
                    qhide_drop()
                    if not self.quick.get().strip():
                        self.quick.insert(0,"Tìm kiếm chức năng..."); self.quick.config(fg=self.C["muted"])
            self.root.after(150,maybe_hide)
        def qfilter(e=None):
            key=strip_accents(self.quick.get().strip()).lower()
            if not key or key=="tim kiem chuc nang...":
                qhide_drop(); return
            self._quick_matches=[it for it in self.quick_items if key in strip_accents(it[0]).lower()]
            if not self._quick_matches:
                qhide_drop(); return
            self.quick_drop.delete(0,"end")
            for label,_ in self._quick_matches: self.quick_drop.insert("end",label)
            self.quick_drop.config(height=min(len(self._quick_matches),6))
            self.quick_drop.place(relx=.5,rely=0,anchor="n",y=68,width=370)
            self.quick_drop.lift()
        def qpick(e=None):
            s=self.quick_drop.curselection()
            idx=s[0] if s else 0
            if idx>=len(self._quick_matches):return
            label,fn=self._quick_matches[idx]
            qhide_drop()
            self.quick.delete(0,"end"); self.quick.insert(0,"Tìm kiếm chức năng...")
            self.quick.config(fg=self.C["muted"])
            self.root.focus(); fn()
        self.quick.bind("<FocusIn>",qfocus_in)
        self.quick.bind("<FocusOut>",qfocus_out)
        self.quick.bind("<KeyRelease>",qfilter)
        self.quick.bind("<Return>",qpick)
        self.quick_drop.bind("<<ListboxSelect>>",qpick)

        self.content=tk.Frame(area,bg=self.C["bg"]); self.content.pack(fill="both",expand=True)
        self.dashboard()

    def menu(self,p,icon,text,cmd):
        row=tk.Frame(p,bg="white",height=40,cursor="hand2")
        row.pack(fill="x",padx=12,pady=2); row.pack_propagate(False)
        ico=tk.Label(row,text=icon,bg="white",fg="#7B8A95",
                     font=("Segoe UI Symbol",14),width=3)
        ico.pack(side="left",padx=(4,0))
        lab=tk.Label(row,text=text,bg="white",fg="#53616C",
                     font=("Segoe UI",9,"bold"))
        lab.pack(side="left")
        def enter(e):
            row.configure(bg="#EAF7EF"); ico.configure(bg="#EAF7EF",fg=self.C["green"]); lab.configure(bg="#EAF7EF",fg=self.C["green"])
        def leave(e):
            row.configure(bg="white"); ico.configure(bg="white",fg="#7B8A95"); lab.configure(bg="white",fg="#53616C")
        def click(e): cmd()
        for w in (row,ico,lab):
            w.bind("<Enter>",enter); w.bind("<Leave>",leave); w.bind("<Button-1>",click)

    def title(self,t,sub=""):
        self.clear(self.content)
        f=tk.Frame(self.content,bg=self.C["bg"]); f.pack(fill="x",padx=28,pady=(22,10))
        tk.Label(f,text=t,bg=self.C["bg"],fg=self.C["dark"],
                 font=("Segoe UI",22,"bold")).pack(anchor="w")
        tk.Label(f,text=sub,bg=self.C["bg"],fg=self.C["muted"]).pack(anchor="w")

    def card(self,p,title,value,desc,col,row):
        f=tk.Frame(p,bg="white",highlightbackground=self.C["border"],highlightthickness=1)
        f.grid(row=row,column=col,padx=7,pady=7,sticky="nsew",ipadx=12,ipady=10)
        tk.Label(f,text=title,bg="white",fg=self.C["muted"],
                 font=("Segoe UI",9,"bold")).pack(anchor="w",padx=12)
        tk.Label(f,text=str(value),bg="white",fg=self.C["dark"],
                 font=("Segoe UI",25,"bold")).pack(anchor="w",padx=12)
        tk.Label(f,text=desc,bg="white",fg=self.C["muted"],
                 font=("Segoe UI",9)).pack(anchor="w",padx=12)

    # ---------------- DASHBOARD ----------------
    def dashboard(self):
        self.title("Tổng quan thư viện","Theo dõi nhanh sách, độc giả, mượn trả và biểu đồ thống kê.")
        c=self.db.conn.cursor()
        c.execute("SELECT COUNT(*) FROM books"); titles=c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(quantity),0) FROM books"); total=c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(available),0) FROM books"); available=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM readers"); readers=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM borrowings WHERE status='Borrowing'"); borrowing=c.fetchone()[0]
        today=datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT COUNT(*) FROM borrowings WHERE status='Borrowing' AND due_date<?",(today,)); overdue=c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(fine),0) FROM borrowings"); fine=c.fetchone()[0]

        cards=tk.Frame(self.content,bg=self.C["bg"]); cards.pack(fill="x",padx=28)
        for i in range(3): cards.grid_columnconfigure(i,weight=1)
        self.card(cards,"ĐẦU SÁCH",titles,"Tổng đầu sách",0,0)
        self.card(cards,"TỔNG BẢN SÁCH",total,"Tổng số bản",1,0)
        self.card(cards,"CÒN TRONG KHO",available,"Có thể cho mượn",2,0)
        self.card(cards,"ĐANG MƯỢN",borrowing,"Phiếu đang mượn",0,1)
        self.card(cards,"QUÁ HẠN",overdue,"Cần xử lý",1,1)
        self.card(cards,"ĐỘC GIẢ",readers,"Tổng độc giả",2,1)

        body=tk.Frame(self.content,bg=self.C["bg"]); body.pack(fill="both",expand=True,padx=28,pady=12)
        chartbox=tk.Frame(body,bg="white",highlightbackground=self.C["border"],highlightthickness=1)
        chartbox.pack(side="left",fill="both",expand=True,padx=(0,7))
        tk.Label(chartbox,text="THỐNG KÊ MƯỢN SÁCH",bg="white",fg=self.C["dark"],font=("Segoe UI",12,"bold")).pack(anchor="w",padx=18,pady=(14,0))
        tk.Label(chartbox,text="6 tháng gần nhất",bg="white",fg=self.C["muted"],font=("Segoe UI",9)).pack(anchor="w",padx=18)
        self.draw_loan_chart(chartbox)

        quick=tk.Frame(body,bg="white",width=290,highlightbackground=self.C["border"],highlightthickness=1)
        quick.pack(side="right",fill="y",padx=(7,0)); quick.pack_propagate(False)
        tk.Label(quick,text="THAO TÁC NHANH",bg="white",fg=self.C["dark"],font=("Segoe UI",12,"bold")).pack(anchor="w",padx=18,pady=(14,10))
        for text,cmd,kind in [("MƯỢN SÁCH",self.borrow,"green"),("TRẢ SÁCH",self.returns,"blue"),("PHIẾU MƯỢN",self.loans,"gray"),("SÁCH QUÁ HẠN",self.overdue,"orange")]:
            self.button(quick,text,cmd,kind,23).pack(padx=18,pady=5,fill="x")
        tk.Label(quick,text="Tổng tiền phạt",bg="white",fg=self.C["muted"],font=("Segoe UI",9,"bold")).pack(anchor="w",padx=18,pady=(20,2))
        tk.Label(quick,text="{:,} VNĐ".format(fine),bg="white",fg=self.C["red"],font=("Segoe UI",18,"bold")).pack(anchor="w",padx=18)
        self.button(quick,"XUẤT PDF",self.export_pdf,"green",23).pack(padx=18,pady=(25,5),fill="x")
        self.button(quick,"XUẤT TXT",self.report,"gray",23).pack(padx=18,pady=5,fill="x")

    def draw_loan_chart(self,parent):
        cv=tk.Canvas(parent,bg="white",highlightthickness=0,height=230)
        cv.pack(fill="both",expand=True,padx=10,pady=10)
        def draw():
            cv.delete("all")
            w=max(cv.winfo_width(),500); h=max(cv.winfo_height(),220)
            c=self.db.conn.cursor(); data=[]
            today=datetime.now().date()
            for k in range(5,-1,-1):
                y=today.year; m=today.month-k
                while m<=0: y-=1; m+=12
                label="{}/{}".format(m,y)
                first=datetime(y,m,1); last=datetime(y,m,calendar.monthrange(y,m)[1])
                c.execute("SELECT COUNT(*) FROM borrowings WHERE borrow_date>=? AND borrow_date<=?",(str(first.date()),str(last.date())))
                data.append((label,c.fetchone()[0]))
            maxv=max([v for _,v in data]+[1]); left=45; bottom=h-35; top=20; usable=h-top-55; gap=18
            bw=(w-left-25-gap*5)/6.0
            cv.create_line(left,top,left,bottom,fill="#C8D1D8"); cv.create_line(left,bottom,w-15,bottom,fill="#C8D1D8")
            for i,(lab,val) in enumerate(data):
                x=left+gap+i*(bw+gap); bh=usable*val/maxv; y=bottom-bh
                cv.create_rectangle(x,y,x+bw,bottom,fill=self.C["green"],outline="")
                cv.create_text(x+bw/2,y-8,text=str(val),fill=self.C["dark"],font=("Segoe UI",8,"bold"))
                cv.create_text(x+bw/2,bottom+14,text=lab,fill=self.C["muted"],font=("Segoe UI",8))
        cv.bind("<Configure>",lambda e:draw())
        parent.after(50,draw)

    # ---------------- BOOKS ----------------
    def books(self):
        self.title("Tra cứu & Danh sách thư viện",
                   "Tìm theo mã sách, tên sách, tác giả hoặc thể loại.")
        bar=tk.Frame(self.content,bg="white",highlightbackground=self.C["border"],highlightthickness=1)
        bar.pack(fill="x",padx=28,pady=8)
        self.bs=tk.Entry(bar,font=("Segoe UI",10),relief="flat",bg="white")
        self.bs.pack(side="left",fill="x",expand=True,padx=12,pady=10,ipady=6)
        self.bs.insert(0,"")
        self.bs.bind("<KeyRelease>", lambda e: self.load_books(self.bs.get().strip()))
        self.button(bar,"⌕  Tìm kiếm",self.search_books,"blue",13).pack(side="left",padx=4)
        self.button(bar,"↻  Làm mới",self.books,"gray",13).pack(side="left",padx=4)
        self.button(bar,"＋  Thêm sách",self.add_book,"green",13).pack(side="left",padx=4)

        body=tk.Frame(self.content,bg=self.C["bg"]); body.pack(fill="both",expand=True,padx=28,pady=5)
        tablebox=tk.Frame(body,bg="white",highlightbackground=self.C["border"],highlightthickness=1)
        tablebox.pack(side="left",fill="both",expand=True,padx=(0,8))
        cols=("id","code","title","author","category","publisher","year","quantity","available")
        self.bt=ttk.Treeview(tablebox,columns=cols,show="headings")
        heads=[("id","#",45),("code","Mã sách",85),("title","Tên sách",220),
               ("author","Tác giả",170),("category","Thể loại",100),("publisher","Nhà XB",130),
               ("year","Năm",60),("quantity","Tổng",60),("available","Còn",60)]
        for col,h,w in heads:
            self.bt.heading(col,text=h); self.bt.column(col,width=w)
        sb=ttk.Scrollbar(tablebox,orient="vertical",command=self.bt.yview); self.bt.configure(yscrollcommand=sb.set)
        self.bt.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
        self.bt.bind("<<TreeviewSelect>>",self.show_book_preview)
        self.bt.bind("<Double-1>",lambda e:self.edit_book())

        preview=tk.Frame(body,bg="white",width=260,highlightbackground=self.C["border"],highlightthickness=1)
        preview.pack(side="right",fill="y"); preview.pack_propagate(False)
        tk.Label(preview,text="THÔNG TIN SÁCH",bg="white",fg="#8A98A3",
                 font=("Segoe UI",8,"bold")).pack(anchor="w",padx=18,pady=(16,8))
        self.cover_label=tk.Label(preview,text="NO COVER",bg="#F0F3F5",fg="#A2ADB5",
                                  width=20,height=11,font=("Segoe UI",10,"bold"))
        self.cover_label.pack(padx=18,pady=5)
        self.preview_title=tk.Label(preview,text="Chọn một cuốn sách",bg="white",fg=self.C["dark"],
                                    font=("Segoe UI",12,"bold"),wraplength=220,justify="center")
        self.preview_title.pack(padx=15,pady=(10,3))
        self.preview_author=tk.Label(preview,text="",bg="white",fg=self.C["muted"],
                                     font=("Segoe UI",9),wraplength=220)
        self.preview_author.pack(padx=15,pady=3)
        self.preview_meta=tk.Label(preview,text="",bg="white",fg=self.C["green"],
                                   font=("Segoe UI",9,"bold"),wraplength=220)
        self.preview_meta.pack(padx=15,pady=5)
        bottom=tk.Frame(preview,bg="white"); bottom.pack(side="bottom",fill="x",padx=15,pady=15)
        self.button(bottom,"SỬA",self.edit_book,"blue",10).pack(side="left")
        self.button(bottom,"XÓA",self.delete_book,"red",10).pack(side="right")
        self.load_books()

    def load_books(self,key=""):
        for x in self.bt.get_children(): self.bt.delete(x)
        c=self.db.conn.cursor()
        if key:
            like="%"+strip_accents(key)+"%"
            c.execute("""SELECT id,code,title,author,category,publisher,year,quantity,available
                         FROM books WHERE unaccent(code) LIKE ? OR unaccent(title) LIKE ? OR unaccent(author) LIKE ? OR unaccent(category) LIKE ?
                         ORDER BY id DESC""",(like,like,like,like))
        else:
            c.execute("SELECT id,code,title,author,category,publisher,year,quantity,available FROM books ORDER BY id DESC")
        for r in c.fetchall(): self.bt.insert("", "end", values=r)
        self.preview_title.config(text="Chọn một cuốn sách"); self.preview_author.config(text=""); self.preview_meta.config(text="")
        self.cover_label.config(image="",text="NO COVER",bg="#F0F3F5")
        self.cover_label.image=None

    def show_book_preview(self,event=None):
        s=self.bt.selection()
        if not s:return
        bid=self.bt.item(s[0])["values"][0]
        c=self.db.conn.cursor(); c.execute("SELECT title,author,category,available,quantity,cover FROM books WHERE id=?",(bid,))
        r=c.fetchone()
        if not r:return
        title,author,cat,av,qty,cover=r
        self.preview_title.config(text=title)
        self.preview_author.config(text="Tác giả: "+str(author))
        self.preview_meta.config(text="{}  •  Còn {}/{} cuốn".format(cat,av,qty))
        self.cover_label.config(image="",text="NO COVER",bg="#F0F3F5")
        self.cover_label.image=None
        if cover and PIL_OK:
            try:
                img=Image.open(cover).convert("RGB")
                img=ImageOps.contain(img,(175,230))
                bg=Image.new("RGB",(190,245),"#F0F3F5")
                x=(190-img.width)//2; y=(245-img.height)//2
                bg.paste(img,(x,y))
                self.cover_label.image=ImageTk.PhotoImage(bg)
                self.cover_label.config(image=self.cover_label.image,text="",bg="#F0F3F5")
            except Exception:
                pass

    def search_books(self):
        self.load_books(self.bs.get().strip())

    def add_book(self):
        self.book_dialog(None)

    def edit_book(self):
        s=self.bt.selection()
        if not s: messagebox.showwarning("Sửa","Hãy chọn sách."); return
        self.book_dialog(self.bt.item(s[0])["values"][0])

    def book_dialog(self,bid):
        d=tk.Toplevel(self.root); d.title("Sách"); d.geometry("720x610")
        d.configure(bg=self.C["bg"]); d.transient(self.root); d.grab_set(); d.resizable(False,True); d.minsize(720,520)
        tk.Label(d,text="SỬA SÁCH" if bid else "THÊM SÁCH",bg=self.C["bg"],
                 fg=self.C["dark"],font=("Segoe UI",20,"bold")).pack(anchor="w",padx=25,pady=20)
        form=tk.Frame(d,bg="white"); form.pack(fill="both",expand=True,padx=25)
        c=self.db.conn.cursor()
        if bid:
            c.execute("""SELECT code,title,author,category,publisher,year,quantity,cover
                         FROM books WHERE id=?""",(bid,))
            data=c.fetchone()
        else: data=("","","","","",datetime.now().year,1,"")
        fields=["Mã sách","Tên sách","Tác giả","Thể loại","Nhà XB","Năm","Số lượng"]
        keys=["code","title","author","category","publisher","year","quantity"]
        es={}
        for i,(lab,key) in enumerate(zip(fields,keys)):
            box=tk.Frame(form,bg="white"); box.grid(row=i//2,column=i%2,padx=10,pady=8,sticky="w")
            tk.Label(box,text=lab,bg="white",font=("Segoe UI",9,"bold")).pack(anchor="w")
            e=tk.Entry(box,width=30,font=("Segoe UI",10)); e.pack(ipady=5,pady=4)
            e.insert(0,str(data[i])); es[key]=e
        cv=tk.StringVar(value=data[7] or "")
        row=tk.Frame(form,bg="white"); row.grid(row=4,column=0,columnspan=2,padx=10,pady=8,sticky="w")
        tk.Label(row,text="Ảnh bìa (đường dẫn tùy chọn)",bg="white").pack(anchor="w")
        tk.Entry(row,textvariable=cv,width=60).pack(side="left",ipady=5,pady=4)
        self.button(row,"CHỌN",lambda:self.choose_cover(cv), "gray",10).pack(side="left",padx=8)
        def save():
            vals=[es[k].get().strip() for k in keys]
            if not vals[0] or not vals[1]:
                messagebox.showwarning("Dữ liệu","Mã và tên sách bắt buộc.",parent=d); return
            try:
                year=int(vals[5]); qty=int(vals[6])
                if qty<0: raise ValueError
            except:
                messagebox.showerror("Dữ liệu","Năm và số lượng không hợp lệ.",parent=d); return
            try:
                if bid:
                    c.execute("SELECT quantity,available FROM books WHERE id=?",(bid,))
                    oldq,olda=c.fetchone()
                    borrowed=oldq-olda
                    if qty<borrowed:
                        messagebox.showerror("Lỗi","Số lượng nhỏ hơn số sách đang mượn.",parent=d); return
                    c.execute("""UPDATE books SET code=?,title=?,author=?,category=?,publisher=?,
                                 year=?,quantity=?,available=?,cover=? WHERE id=?""",
                              (*vals[:5],year,qty,qty-borrowed,cv.get(),bid))
                else:
                    c.execute("""INSERT INTO books(code,title,author,category,publisher,year,quantity,available,cover)
                                 VALUES(?,?,?,?,?,?,?,?,?)""",
                              (*vals[:5],year,qty,qty,cv.get()))
                self.db.conn.commit(); d.destroy(); self.books()
            except sqlite3.IntegrityError:
                messagebox.showerror("Lỗi","Mã sách đã tồn tại.",parent=d)
        buttons=tk.Frame(d,bg=self.C["bg"]); buttons.pack(fill="x",padx=25,pady=15)
        self.button(buttons,"HỦY",d.destroy,"gray",16).pack(side="right",ipady=6)
        self.button(buttons,"LƯU",save,width=16).pack(side="right",padx=8,ipady=6)

    def choose_cover(self,var):
        p=filedialog.askopenfilename(filetypes=[("Ảnh bìa","*.png *.jpg *.jpeg *.gif"),("Tất cả","*.*")])
        if p: var.set(p)

    def delete_book(self):
        s=self.bt.selection()
        if not s: return
        bid=self.bt.item(s[0])["values"][0]
        c=self.db.conn.cursor()
        c.execute("SELECT COUNT(*) FROM borrowings WHERE book_id=? AND status='Borrowing'",(bid,))
        if c.fetchone()[0]:
            messagebox.showerror("Lỗi","Sách đang được mượn."); return
        if messagebox.askyesno("Xác nhận","Xóa sách này?"):
            c.execute("DELETE FROM books WHERE id=?",(bid,)); self.db.conn.commit(); self.load_books()

    # ---------------- READERS ----------------
    def readers(self):
        self.title("Quản lý độc giả","Thêm, sửa, xóa và tìm kiếm độc giả.")
        bar=tk.Frame(self.content,bg="white"); bar.pack(fill="x",padx=28,pady=8)
        self.rs=tk.Entry(bar,font=("Segoe UI",10),relief="solid",bd=1)
        self.rs.pack(side="left",fill="x",expand=True,padx=12,pady=10,ipady=6)
        self.button(bar,"TÌM KIẾM",self.search_readers,width=13).pack(side="left",padx=4)
        self.button(bar,"THÊM ĐỘC GIẢ",lambda:self.reader_dialog(None),width=15).pack(side="left",padx=4)
        wrap=tk.Frame(self.content,bg="white"); wrap.pack(fill="both",expand=True,padx=28,pady=8)
        self.rt=ttk.Treeview(wrap,columns=("id","code","name","phone","address"),show="headings")
        for col,h,w in [("id","ID",50),("code","Mã ĐG",90),("name","Họ tên",220),("phone","SĐT",150),("address","Địa chỉ",250)]:
            self.rt.heading(col,text=h); self.rt.column(col,width=w)
        self.rt.pack(fill="both",expand=True)
        b=tk.Frame(self.content,bg=self.C["bg"]); b.pack(fill="x",padx=28,pady=10)
        self.button(b,"SỬA",self.edit_reader,"blue",12).pack(side="left")
        self.button(b,"XÓA",self.delete_reader,"red",12).pack(side="left",padx=8)
        self.load_readers()

    def load_readers(self,key=""):
        for x in self.rt.get_children(): self.rt.delete(x)
        c=self.db.conn.cursor()
        if key:
            q="%"+strip_accents(key)+"%"; c.execute("""SELECT id,code,name,phone,address FROM readers
                         WHERE unaccent(code) LIKE ? OR unaccent(name) LIKE ? OR unaccent(phone) LIKE ? ORDER BY id DESC""",(q,q,q))
        else: c.execute("SELECT id,code,name,phone,address FROM readers ORDER BY id DESC")
        for r in c.fetchall(): self.rt.insert("", "end", values=r)

    def search_readers(self): self.load_readers(self.rs.get().strip())

    def reader_dialog(self,rid):
        d=tk.Toplevel(self.root); d.title("Độc giả"); d.geometry("500x460"); d.configure(bg=self.C["bg"])
        d.transient(self.root); d.grab_set(); d.resizable(False,True); d.minsize(500,400)
        tk.Label(d,text="SỬA ĐỘC GIẢ" if rid else "THÊM ĐỘC GIẢ",bg=self.C["bg"],
                 fg=self.C["dark"],font=("Segoe UI",20,"bold")).pack(anchor="w",padx=25,pady=20)
        f=tk.Frame(d,bg="white"); f.pack(fill="both",expand=True,padx=25)
        c=self.db.conn.cursor()
        if rid:
            c.execute("SELECT code,name,phone,address FROM readers WHERE id=?",(rid,)); data=c.fetchone()
        else: data=("","","","")
        es=[]
        for i,(lab,val) in enumerate(zip(["Mã độc giả","Họ tên","SĐT","Địa chỉ"],data)):
            tk.Label(f,text=lab,bg="white",font=("Segoe UI",9,"bold")).pack(anchor="w",padx=12,pady=(10,0))
            e=tk.Entry(f,width=45,font=("Segoe UI",10)); e.pack(padx=12,ipady=5); e.insert(0,str(val)); es.append(e)
        def save():
            vals=[e.get().strip() for e in es]
            if not vals[0] or not vals[1]: messagebox.showwarning("Dữ liệu","Mã và họ tên bắt buộc.",parent=d); return
            try:
                if rid: c.execute("UPDATE readers SET code=?,name=?,phone=?,address=? WHERE id=?",(*vals,rid))
                else: c.execute("INSERT INTO readers(code,name,phone,address) VALUES(?,?,?,?)",vals)
                self.db.conn.commit(); d.destroy(); self.readers()
            except sqlite3.IntegrityError: messagebox.showerror("Lỗi","Mã độc giả đã tồn tại.",parent=d)
        b=tk.Frame(d,bg=self.C["bg"]); b.pack(fill="x",padx=25,pady=15)
        self.button(b,"HỦY",d.destroy,"gray",16).pack(side="right",ipady=6)
        self.button(b,"LƯU",save,width=16).pack(side="right",padx=8,ipady=6)

    def edit_reader(self):
        s=self.rt.selection()
        if not s: messagebox.showwarning("Sửa","Hãy chọn độc giả."); return
        self.reader_dialog(self.rt.item(s[0])["values"][0])

    def delete_reader(self):
        s=self.rt.selection()
        if not s: return
        rid=self.rt.item(s[0])["values"][0]
        c=self.db.conn.cursor(); c.execute("SELECT COUNT(*) FROM borrowings WHERE reader_id=? AND status='Borrowing'",(rid,))
        if c.fetchone()[0]: messagebox.showerror("Lỗi","Độc giả đang mượn sách."); return
        if messagebox.askyesno("Xác nhận","Xóa độc giả này?"):
            c.execute("DELETE FROM readers WHERE id=?",(rid,)); self.db.conn.commit(); self.load_readers()

    # ---------------- BORROW ----------------
    def borrow(self):
        self.title("Mượn sách","Tạo phiếu mượn và tự động cập nhật kho.")
        f=tk.Frame(self.content,bg="white"); f.pack(fill="x",padx=28,pady=10)
        self.borrow_r=tk.StringVar(); self.borrow_b=tk.StringVar()
        tk.Label(f,text="Độc giả",bg="white",font=("Segoe UI",10,"bold")).grid(row=0,column=0,padx=20,pady=12)
        self.rc=ttk.Combobox(f,textvariable=self.borrow_r,width=50,state="readonly"); self.rc.grid(row=0,column=1,pady=12)
        tk.Label(f,text="Sách",bg="white",font=("Segoe UI",10,"bold")).grid(row=1,column=0,padx=20,pady=12)
        self.bc=ttk.Combobox(f,textvariable=self.borrow_b,width=50,state="readonly"); self.bc.grid(row=1,column=1,pady=12)
        tk.Label(f,text="Số ngày mượn",bg="white",font=("Segoe UI",10,"bold")).grid(row=2,column=0,padx=20,pady=12)
        self.days=tk.Entry(f,width=20); self.days.insert(0,"14"); self.days.grid(row=2,column=1,sticky="w",pady=12)
        self.button(f,"XÁC NHẬN MƯỢN",self.do_borrow,width=22).grid(row=3,column=1,sticky="w",pady=18)
        self.rmap={}; self.bmap={}; self.load_borrow()

    def load_borrow(self):
        c=self.db.conn.cursor()
        c.execute("SELECT id,code,name FROM readers ORDER BY name")
        rv=[]
        for i,code,name in c.fetchall(): self.rmap[code+" - "+name]=i; rv.append(code+" - "+name)
        self.rc["values"]=rv
        if rv:self.rc.current(0)
        c.execute("SELECT id,code,title,available FROM books WHERE available>0 ORDER BY title")
        bv=[]
        for i,code,title,av in c.fetchall():
            x=code+" - "+title+" (Còn "+str(av)+")"; self.bmap[x]=i; bv.append(x)
        self.bc["values"]=bv
        if bv:self.bc.current(0)

    def do_borrow(self):
        if not self.rc.get() or not self.bc.get(): messagebox.showwarning("Mượn","Hãy chọn độc giả và sách."); return
        try: days=int(self.days.get()); assert days>0
        except: messagebox.showerror("Mượn","Số ngày không hợp lệ."); return
        c=self.db.conn.cursor(); bid=self.bmap[self.bc.get()]; rid=self.rmap[self.rc.get()]
        today=datetime.now().date(); due=today+timedelta(days=days)
        c.execute("""INSERT INTO borrowings(book_id,reader_id,borrow_date,due_date,return_date,fine,status)
                     VALUES(?,?,?,?,?,?,?)""",(bid,rid,str(today),str(due),"",0,"Borrowing"))
        c.execute("UPDATE books SET available=available-1 WHERE id=?",(bid,))
        self.db.conn.commit()
        messagebox.showinfo("Thành công","Đã tạo phiếu mượn. Hạn trả: "+due.strftime("%d/%m/%Y"))
        self.borrow()

    # ---------------- LOAN MANAGEMENT ----------------
    def loans(self):
        self.title("Quản lý phiếu mượn","Theo dõi tất cả phiếu mượn, trạng thái, hạn trả và tiền phạt.")
        bar=tk.Frame(self.content,bg="white",highlightbackground=self.C["border"],highlightthickness=1)
        bar.pack(fill="x",padx=28,pady=8)
        tk.Label(bar,text="Trạng thái",bg="white",fg=self.C["muted"],font=("Segoe UI",9,"bold")).pack(side="left",padx=(15,5))
        self.loan_filter=ttk.Combobox(bar,values=("Tất cả","Đang mượn","Đã trả","Quá hạn"),state="readonly",width=14)
        self.loan_filter.current(0); self.loan_filter.pack(side="left",pady=9); self.loan_filter.bind("<<ComboboxSelected>>",lambda e:self.load_loans())
        self.loan_search=tk.Entry(bar,width=35,font=("Segoe UI",10),relief="flat",bg="#F7F9FA")
        self.loan_search.pack(side="left",fill="x",expand=True,padx=15,pady=8,ipady=6)
        self.loan_search.bind("<KeyRelease>",lambda e:self.load_loans())
        self.button(bar,"↻ Làm mới",self.loans,"gray",12).pack(side="right",padx=5)
        wrap=tk.Frame(self.content,bg="white",highlightbackground=self.C["border"],highlightthickness=1); wrap.pack(fill="both",expand=True,padx=28,pady=8)
        cols=("id","reader","book","borrow","due","return","fine","status")
        self.lt=ttk.Treeview(wrap,columns=cols,show="headings")
        heads=[("id","ID",45),("reader","Độc giả",180),("book","Sách",230),("borrow","Ngày mượn",100),("due","Hạn trả",100),("return","Ngày trả",100),("fine","Tiền phạt",110),("status","Trạng thái",110)]
        for col,h,w in heads:self.lt.heading(col,text=h);self.lt.column(col,width=w)
        sb=ttk.Scrollbar(wrap,orient="vertical",command=self.lt.yview);self.lt.configure(yscrollcommand=sb.set)
        self.lt.pack(side="left",fill="both",expand=True);sb.pack(side="right",fill="y")
        b=tk.Frame(self.content,bg=self.C["bg"]);b.pack(fill="x",padx=28,pady=10)
        self.button(b,"TRẢ PHIẾU ĐÃ CHỌN",self.return_selected_loan,"blue",20).pack(side="left")
        self.button(b,"XUẤT PHIẾU MƯỢN PDF",self.export_loan_receipt,"green",21).pack(side="left",padx=8)
        self.button(b,"XÓA PHIẾU ĐÃ TRẢ",self.delete_returned_loan,"red",19).pack(side="left",padx=8)
        self.load_loans()

    def load_loans(self):
        if not hasattr(self,"lt"): return
        for x in self.lt.get_children():self.lt.delete(x)
        filt=self.loan_filter.get() if hasattr(self,"loan_filter") else "Tất cả"
        key=self.loan_search.get().strip() if hasattr(self,"loan_search") else ""
        c=self.db.conn.cursor(); c.execute("""SELECT b.id,r.name,bo.title,b.borrow_date,b.due_date,b.return_date,b.fine,b.status
                     FROM borrowings b JOIN readers r ON r.id=b.reader_id JOIN books bo ON bo.id=b.book_id ORDER BY b.id DESC""")
        today=datetime.now().date()
        for rid,name,title,borrow,due,ret,fine,status in c.fetchall():
            late=status=="Borrowing" and datetime.strptime(due,"%Y-%m-%d").date()<today
            display="Quá hạn" if late else ("Đang mượn" if status=="Borrowing" else "Đã trả")
            if filt!="Tất cả" and display!=filt: continue
            if key and strip_accents(key).lower() not in strip_accents(str(name)+" "+str(title)).lower(): continue
            self.lt.insert("","end",values=(rid,name,title,self.fd(borrow),self.fd(due),self.fd(ret) if ret else "-","{:,} VNĐ".format(fine or 0),display))

    def export_loan_receipt(self):
        """Xuất phiếu mượn PDF để in và giao cho độc giả."""
        if not REPORTLAB_OK:
            messagebox.showerror("Thiếu thư viện", "Cần cài ReportLab trước khi xuất phiếu:\n\npip install reportlab")
            return
        selected = self.lt.selection()
        if not selected:
            messagebox.showwarning("Phiếu mượn", "Hãy chọn một phiếu mượn trong danh sách trước khi xuất.")
            return
        loan_id = self.lt.item(selected[0])["values"][0]
        c = self.db.conn.cursor()
        c.execute("""SELECT b.id,b.borrow_date,b.due_date,b.return_date,b.fine,b.status,
                          r.code,r.name,r.phone,r.address,bo.code,bo.title,bo.author,bo.publisher
                   FROM borrowings b JOIN readers r ON r.id=b.reader_id
                   JOIN books bo ON bo.id=b.book_id WHERE b.id=?""", (loan_id,))
        row = c.fetchone()
        if not row:
            messagebox.showerror("Phiếu mượn", "Không tìm thấy dữ liệu của phiếu mượn này.")
            return
        (lid, borrow_date, due_date, return_date, fine, status,
         reader_code, reader_name, phone, address, book_code, book_title, author, publisher) = row
        path = filedialog.asksaveasfilename(
            title="Xuất phiếu mượn để in", defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")], initialfile="phieu_muon_{:05d}.pdf".format(lid))
        if not path:
            return
        try:
            fn, fb = pdf_fonts()
            from reportlab.lib.pagesizes import A5
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
            from xml.sax.saxutils import escape
            doc = SimpleDocTemplate(path, pagesize=A5, rightMargin=26, leftMargin=26,
                                    topMargin=24, bottomMargin=24,
                                    title="Phieu muon sach #{:05d}".format(lid), author="Library Manager")
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle("LoanReceiptTitle", parent=styles["Title"], fontName=fb,
                fontSize=16, leading=19, alignment=TA_CENTER, textColor=colors.HexColor("#246B45"), spaceAfter=4)
            center_style = ParagraphStyle("LoanReceiptCenter", parent=styles["Normal"], fontName=fn,
                fontSize=8, leading=11, alignment=TA_CENTER)
            body_style = ParagraphStyle("LoanReceiptBody", parent=styles["Normal"], fontName=fn,
                fontSize=8.5, leading=12, spaceAfter=2)
            small_style = ParagraphStyle("LoanReceiptSmall", parent=styles["Normal"], fontName=fn,
                fontSize=7.5, leading=10)
            section_style = ParagraphStyle("LoanReceiptSection", parent=styles["Heading2"], fontName=fb,
                fontSize=9.5, leading=12, textColor=colors.HexColor("#246B45"), spaceBefore=7, spaceAfter=4)
            safe = lambda value: escape(str(value if value not in (None, "") else "—"))
            story = [Paragraph("PHIẾU MƯỢN SÁCH", title_style),
                     Paragraph("THƯ VIỆN • PHIẾU GIAO CHO ĐỘC GIẢ", center_style), Spacer(1, 7)]
            info = [
                [Paragraph("<b>Mã phiếu:</b>", body_style), Paragraph("PM-{:05d}".format(lid), body_style)],
                [Paragraph("<b>Ngày lập:</b>", body_style), Paragraph(datetime.now().strftime("%d/%m/%Y %H:%M"), body_style)],
                [Paragraph("<b>Trạng thái:</b>", body_style), Paragraph("Đã trả" if status == "Returned" else "Đang mượn", body_style)],
            ]
            table = Table(info, colWidths=[88, 175])
            table.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),4),
                                       ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
            story.extend([table, Paragraph("THÔNG TIN ĐỘC GIẢ", section_style)])
            def detail_table(rows):
                data = [[Paragraph("<b>{}</b>".format(label), small_style), Paragraph(safe(value), body_style)]
                        for label, value in rows]
                t = Table(data, colWidths=[88, 175])
                t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#D9E2E8")),
                    ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#F2F7F4")),("VALIGN",(0,0),(-1,-1),"TOP"),
                    ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
                    ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
                return t
            story.append(detail_table([("Mã độc giả",reader_code),("Họ và tên",reader_name),
                                       ("Số điện thoại",phone),("Địa chỉ",address)]))
            story.append(Paragraph("THÔNG TIN SÁCH", section_style))
            story.append(detail_table([("Mã sách",book_code),("Tên sách",book_title),
                                       ("Tác giả",author),("Nhà xuất bản",publisher)]))
            story.append(Paragraph("THỜI HẠN MƯỢN", section_style))
            dates = [[Paragraph("<b>Ngày mượn</b>",small_style),Paragraph("<b>Hạn trả</b>",small_style),Paragraph("<b>Ngày trả</b>",small_style)],
                     [Paragraph(self.fd(borrow_date),body_style),Paragraph(self.fd(due_date),body_style),
                      Paragraph(self.fd(return_date) if return_date else "Chưa trả",body_style)]]
            dt = Table(dates, colWidths=[87,87,89])
            dt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EAF7EF")),
                ("GRID",(0,0),(-1,-1),0.35,colors.HexColor("#D9E2E8")),("ALIGN",(0,0),(-1,-1),"CENTER"),
                ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),5),
                ("BOTTOMPADDING",(0,0),(-1,-1),5)]))
            story.extend([dt, Spacer(1,6), Paragraph("<b>Tiền phạt hiện ghi nhận:</b> {:,} VNĐ".format(fine or 0),body_style),
                Spacer(1,5), Paragraph("<b>LƯU Ý</b>",section_style),
                Paragraph("• Vui lòng trả sách đúng hạn. <br/>• Giữ phiếu để đối chiếu khi trả sách. <br/>• Liên hệ nhân viên thư viện nếu cần gia hạn.",body_style),
                Spacer(1,13)])
            signatures = Table([[Paragraph("<b>ĐỘC GIẢ</b><br/><font size='7'>(Ký và ghi rõ họ tên)</font><br/><br/><br/>........................",center_style),
                                Paragraph("<b>NHÂN VIÊN THƯ VIỆN</b><br/><font size='7'>(Ký và ghi rõ họ tên)</font><br/><br/><br/>........................",center_style)]],
                               colWidths=[131,132])
            signatures.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(0,0),(-1,-1),"CENTER")]))
            story.append(KeepTogether(signatures))
            doc.build(story)
            messagebox.showinfo("Xuất phiếu mượn", "Đã tạo phiếu mượn PDF để in cho độc giả:\n{}".format(path))
        except Exception as exc:
            messagebox.showerror("Lỗi xuất phiếu", "Không thể tạo phiếu PDF.\nChi tiết: {}".format(exc))

    def return_selected_loan(self):
        s=self.lt.selection()
        if not s: messagebox.showwarning("Phiếu mượn","Hãy chọn một phiếu."); return
        vals=self.lt.item(s[0])["values"]
        if vals[7]!="Đang mượn" and vals[7]!="Quá hạn": messagebox.showinfo("Phiếu mượn","Phiếu này đã trả."); return
        bid=vals[0]; c=self.db.conn.cursor(); c.execute("SELECT book_id,due_date FROM borrowings WHERE id=?",(bid,)); row=c.fetchone()
        if not row:return
        book,due=row; today=datetime.now().date(); late=max((today-datetime.strptime(due,"%Y-%m-%d").date()).days,0); fine=late*FINE_PER_DAY
        if not messagebox.askyesno("Xác nhận","Trả sách và tính phạt {:,} VNĐ?".format(fine)):return
        c.execute("UPDATE borrowings SET return_date=?,fine=?,status='Returned' WHERE id=?",(str(today),fine,bid));c.execute("UPDATE books SET available=available+1 WHERE id=?",(book,));self.db.conn.commit();self.load_loans()

    def delete_returned_loan(self):
        s=self.lt.selection()
        if not s:return
        vals=self.lt.item(s[0])["values"]
        if vals[7]!="Đã trả":messagebox.showwarning("Xóa","Chỉ được xóa phiếu đã trả.");return
        if messagebox.askyesno("Xác nhận","Xóa phiếu này? "):
            c=self.db.conn.cursor();c.execute("DELETE FROM borrowings WHERE id=?",(vals[0],));self.db.conn.commit();self.load_loans()

    # ---------------- RETURN / OVERDUE ----------------
    def returns(self):
        self.title("Trả sách","Danh sách sách đang được mượn.")
        wrap=tk.Frame(self.content,bg="white"); wrap.pack(fill="both",expand=True,padx=28,pady=10)
        self.tret=ttk.Treeview(wrap,columns=("id","reader","phone","book","borrow","due","late"),show="headings")
        for col,h,w in [("id","ID",45),("reader","Độc giả",170),("phone","SĐT",120),("book","Sách",230),
                        ("borrow","Ngày mượn",100),("due","Hạn trả",100),("late","Quá hạn",80)]:
            self.tret.heading(col,text=h); self.tret.column(col,width=w)
        self.tret.pack(fill="both",expand=True)
        b=tk.Frame(self.content,bg=self.C["bg"]); b.pack(fill="x",padx=28,pady=10)
        self.button(b,"XÁC NHẬN TRẢ SÁCH",self.do_return,width=22).pack(side="left")
        self.load_returns()

    def load_returns(self):
        c=self.db.conn.cursor()
        c.execute("""SELECT b.id,r.name,r.phone,bo.title,b.borrow_date,b.due_date
                     FROM borrowings b JOIN readers r ON r.id=b.reader_id
                     JOIN books bo ON bo.id=b.book_id WHERE b.status='Borrowing'
                     ORDER BY b.due_date""")
        today=datetime.now().date()
        for r in c.fetchall():
            due=datetime.strptime(r[5],"%Y-%m-%d").date(); late=max((today-due).days,0)
            self.tret.insert("", "end", values=(r[0],r[1],r[2],r[3],self.fd(r[4]),self.fd(r[5]),
                                                str(late)+" ngày" if late else "-"))

    def do_return(self):
        s=self.tret.selection()
        if not s: messagebox.showwarning("Trả","Hãy chọn phiếu."); return
        bid=self.tret.item(s[0])["values"][0]; c=self.db.conn.cursor()
        c.execute("SELECT book_id,due_date FROM borrowings WHERE id=?",(bid,)); book,due=c.fetchone()
        today=datetime.now().date(); late=max((today-datetime.strptime(due,"%Y-%m-%d").date()).days,0); fine=late*FINE_PER_DAY
        if not messagebox.askyesno("Xác nhận","Tiền phạt: {:,} VNĐ\nXác nhận trả?".format(fine)): return
        c.execute("UPDATE borrowings SET return_date=?,fine=?,status='Returned' WHERE id=?",(str(today),fine,bid))
        c.execute("UPDATE books SET available=available+1 WHERE id=?",(book,)); self.db.conn.commit()
        messagebox.showinfo("Thành công","Đã trả sách. Tiền phạt: {:,} VNĐ".format(fine)); self.returns()

    def overdue(self):
        self.title("Sách quá hạn","Những phiếu đang mượn đã vượt quá hạn trả.")
        wrap=tk.Frame(self.content,bg="white"); wrap.pack(fill="both",expand=True,padx=28,pady=10)
        t=ttk.Treeview(wrap,columns=("id","reader","phone","book","due","late","fine"),show="headings")
        for col,h,w in [("id","ID",45),("reader","Độc giả",170),("phone","SĐT",120),("book","Sách",230),
                        ("due","Hạn trả",100),("late","Số ngày",80),("fine","Tiền phạt",120)]:
            t.heading(col,text=h); t.column(col,width=w)
        t.pack(fill="both",expand=True)
        c=self.db.conn.cursor()
        c.execute("""SELECT b.id,r.name,r.phone,bo.title,b.due_date FROM borrowings b
                     JOIN readers r ON r.id=b.reader_id JOIN books bo ON bo.id=b.book_id
                     WHERE b.status='Borrowing'""")
        today=datetime.now().date(); count=0
        for r in c.fetchall():
            late=(today-datetime.strptime(r[4],"%Y-%m-%d").date()).days
            if late>0:
                count+=1; t.insert("", "end",values=(r[0],r[1],r[2],r[3],self.fd(r[4]),late,
                                                      "{:,} VNĐ".format(late*FINE_PER_DAY)))
        if count==0:
            tk.Label(self.content,text="✓  Hiện tại không có sách quá hạn.",bg=self.C["bg"],
                     fg=self.C["green"],font=("Segoe UI",13,"bold")).pack(pady=15)

    # ---------------- USERS ----------------
    def users(self):
        self.title("Quản lý tài khoản","Chức năng chỉ dành cho Admin.")
        f=tk.Frame(self.content,bg="white"); f.pack(fill="x",padx=28,pady=10)
        e1=tk.Entry(f,width=22); e2=tk.Entry(f,width=22,show="*")
        e1.grid(row=0,column=0,padx=10,pady=12,ipady=5); e2.grid(row=0,column=1,padx=10,pady=12,ipady=5)
        role=ttk.Combobox(f,values=("Admin","Librarian"),state="readonly",width=15); role.current(1); role.grid(row=0,column=2,padx=10)
        def add():
            try:
                c=self.db.conn.cursor(); c.execute("INSERT INTO users(username,password,role) VALUES(?,?,?)",
                                                   (e1.get().strip(),hash_pw(e2.get()),role.get()))
                self.db.conn.commit(); self.users()
            except sqlite3.IntegrityError: messagebox.showerror("Lỗi","Username đã tồn tại.")
        self.button(f,"THÊM",add,width=12).grid(row=0,column=3,padx=10)
        wrap=tk.Frame(self.content,bg="white"); wrap.pack(fill="both",expand=True,padx=28,pady=10)
        self.ut=ttk.Treeview(wrap,columns=("id","username","role","status"),show="headings")
        for col,h,w in [("id","ID",60),("username","Username",200),("role","Vai trò",160),("status","Trạng thái",150)]:
            self.ut.heading(col,text=h); self.ut.column(col,width=w)
        self.ut.pack(fill="both",expand=True); self.load_users()

    def load_users(self):
        for x in self.ut.get_children(): self.ut.delete(x)
        c=self.db.conn.cursor(); c.execute("SELECT id,username,role,status FROM users")
        for r in c.fetchall(): self.ut.insert("", "end",values=r)

    # ---------------- REPORT ----------------
    def report_data(self):
        c=self.db.conn.cursor(); today=str(datetime.now().date())
        c.execute("SELECT COUNT(*) FROM books"); titles=c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(quantity),0) FROM books"); total=c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(available),0) FROM books"); available=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM readers"); readers=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM borrowings WHERE status='Borrowing'"); borrowing=c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM borrowings WHERE status='Borrowing' AND due_date<?",(today,)); overdue=c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(fine),0) FROM borrowings"); fine=c.fetchone()[0]
        c.execute("""SELECT bo.code,bo.title,r.name,b.borrow_date,b.due_date,b.return_date,b.fine,b.status
                     FROM borrowings b JOIN books bo ON bo.id=b.book_id JOIN readers r ON r.id=b.reader_id ORDER BY b.id DESC""")
        loans=c.fetchall()
        return titles,total,available,readers,borrowing,overdue,fine,loans

    def report(self):
        path=filedialog.asksaveasfilename(defaultextension=".txt",filetypes=[("Text","*.txt")],initialfile="bao_cao_thu_vien.txt")
        if not path:return
        titles,total,available,readers,borrowing,overdue,fine,loans=self.report_data()
        text="LIBRARY MANAGER - BÁO CÁO\n"+"="*70+"\n"
        text+="Thời gian: "+datetime.now().strftime("%d/%m/%Y %H:%M")+"\n\n"
        text+="Đầu sách: {}\nTổng bản sách: {}\nCòn trong kho: {}\nĐộc giả: {}\nĐang mượn: {}\nQuá hạn: {}\nTổng tiền phạt: {:,} VNĐ\n\n".format(titles,total,available,readers,borrowing,overdue,fine)
        text+="DANH SÁCH PHIẾU MƯỢN\n"+"-"*70+"\n"
        for r in loans:text+="{} | {} | {} | {} -> {} | {} | {:,} VNĐ | {}\n".format(r[0],r[1],r[2],self.fd(r[3]),self.fd(r[4]),self.fd(r[5]) if r[5] else "-",r[6] or 0,r[7])
        Path(path).write_text(text,encoding="utf-8")
        messagebox.showinfo("Báo cáo","Đã xuất TXT thành công.")

    def export_pdf(self):
        if not REPORTLAB_OK:
            messagebox.showerror("Thiếu thư viện","Cần cài reportlab: pip install reportlab");return
        path=filedialog.asksaveasfilename(defaultextension=".pdf",filetypes=[("PDF","*.pdf")],initialfile="bao_cao_thu_vien.pdf")
        if not path:return
        titles,total,available,readers,borrowing,overdue,fine,loans=self.report_data()
        doc=SimpleDocTemplate(path,pagesize=A4,rightMargin=28,leftMargin=28,topMargin=28,bottomMargin=28)
        fn,fb=pdf_fonts()
        styles=getSampleStyleSheet(); normal=ParagraphStyle("VNNormal",parent=styles["Normal"],fontName=fn); h2=ParagraphStyle("VNH2",parent=styles["Heading2"],fontName=fb); title=ParagraphStyle("VNTitle",parent=styles["Title"],fontName=fb,fontSize=18,alignment=TA_CENTER,spaceAfter=12)
        story=[Paragraph("BÁO CÁO QUẢN LÝ THƯ VIỆN",title),Paragraph("Thời gian: "+datetime.now().strftime("%d/%m/%Y %H:%M"),normal),Spacer(1,10)]
        summary=[["Chỉ số","Giá trị"],["Đầu sách",titles],["Tổng bản sách",total],["Còn trong kho",available],["Độc giả",readers],["Đang mượn",borrowing],["Quá hạn",overdue],["Tổng tiền phạt","{:,} VNĐ".format(fine)]]
        t=Table(summary,colWidths=[250,250]);t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2E8B57")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.5,colors.grey),("FONTNAME",(0,0),(-1,-1),fn),("FONTNAME",(0,0),(-1,0),fb),("ALIGN",(1,1),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F4F8F6")])]))
        story += [t,Spacer(1,18),Paragraph("DANH SÁCH PHIẾU MƯỢN",h2)]
        data=[["Mã","Sách","Độc giả","Mượn","Hạn","Trả","Phạt","Trạng thái"]]
        for r in loans:data.append([r[0],r[1][:22],r[2][:18],self.fd(r[3]),self.fd(r[4]),self.fd(r[5]) if r[5] else "-","{:,}".format(r[6] or 0),r[7]])
        table=Table(data,colWidths=[28,115,95,55,55,55,55,60],repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2E8B57")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.3,colors.grey),("FONTNAME",(0,0),(-1,-1),fn),("FONTNAME",(0,0),(-1,0),fb),("FONTSIZE",(0,0),(-1,-1),7),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
        story.append(table);doc.build(story)
        messagebox.showinfo("Báo cáo","Đã xuất PDF thành công.")

    def fd(self,s):
        try:return datetime.strptime(s,"%Y-%m-%d").strftime("%d/%m/%Y")
        except:return s

    def logout(self):
        if messagebox.askyesno("Đăng xuất","Bạn có chắc muốn đăng xuất?"):
            self.user=None; self.role=None; self.login()

    def exit(self):
        self.db.conn.close(); self.root.destroy()

if __name__=="__main__":
    root=tk.Tk()
    LibraryApp(root)
    root.mainloop()