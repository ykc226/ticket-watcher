import threading
import time
import requests
import json
import os
import tkinter as tk
from tkinter import scrolledtext, messagebox

VERSION = "1.0"

class WatcherApp:
    def __init__(self, root):
        self.root = root
        root.title(f"Ticket Watcher {VERSION}")

        tk.Label(root, text="Ticket URL:").grid(row=0, column=0, sticky="e")
        self.url_var = tk.StringVar(value=os.environ.get("TICKET_URL",""))
        tk.Entry(root, width=60, textvariable=self.url_var).grid(row=0, column=1, columnspan=3, padx=4, pady=4)

        tk.Label(root, text="Keyword (or leave empty for JSON 'available'):").grid(row=1, column=0, sticky="e")
        self.keyword_var = tk.StringVar()
        tk.Entry(root, width=40, textvariable=self.keyword_var).grid(row=1, column=1, padx=4, pady=4)

        tk.Label(root, text="Interval (sec):").grid(row=1, column=2, sticky="e")
        self.interval_var = tk.StringVar(value=os.environ.get("CHECK_INTERVAL","60"))
        tk.Entry(root, width=8, textvariable=self.interval_var).grid(row=1, column=3, padx=4, pady=4)

        tk.Label(root, text="Telegram Bot Token:").grid(row=2, column=0, sticky="e")
        self.bot_var = tk.StringVar(value=os.environ.get("TELEGRAM_BOT_TOKEN",""))
        tk.Entry(root, width=40, textvariable=self.bot_var, show="*").grid(row=2, column=1, padx=4, pady=4)

        tk.Label(root, text="Telegram Chat ID:").grid(row=2, column=2, sticky="e")
        self.chat_var = tk.StringVar(value=os.environ.get("TELEGRAM_CHAT_ID",""))
        tk.Entry(root, width=18, textvariable=self.chat_var).grid(row=2, column=3, padx=4, pady=4)

        self.start_btn = tk.Button(root, text="Start", command=self.start)
        self.start_btn.grid(row=3, column=1, pady=6)
        tk.Button(root, text="Stop", command=self.stop).grid(row=3, column=2, pady=6)

        self.log = scrolledtext.ScrolledText(root, width=80, height=20)
        self.log.grid(row=4, column=0, columnspan=4, padx=6, pady=6)

        self.running = False
        self.thread = None

    def log_msg(self, *parts):
        msg = " ".join(str(p) for p in parts)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.log.see(tk.END)
        print(msg)

    def start(self):
        if self.running:
            return
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("Missing URL","Please provide the ticket URL to monitor.")
            return
        try:
            interval = int(self.interval_var.get())
            if interval < 5:
                raise ValueError()
        except Exception:
            messagebox.showwarning("Interval","Please provide a valid interval (>=5 seconds)")
            return
        self.running = True
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()
        self.log_msg("Started monitoring", url, "every", interval, "sec")

    def stop(self):
        if not self.running:
            return
        self.running = False
        self.log_msg("Stopping...")

    def send_telegram(self, text):
        token = self.bot_var.get().strip()
        chat_id = self.chat_var.get().strip()
        if not token or not chat_id:
            self.log_msg("Telegram not configured (missing token/chat id).")
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            resp = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=10)
            if resp.status_code == 200:
                self.log_msg("Telegram sent")
            else:
                self.log_msg("Telegram error", resp.status_code, resp.text)
        except Exception as e:
            self.log_msg("Telegram exception", e)

    def check_once(self, url, keyword):
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            content_type = resp.headers.get('Content-Type','')
            # try json
            if 'application/json' in content_type:
                data = resp.json()
                # common fields
                if isinstance(data, dict):
                    if 'available' in data:
                        val = data.get('available')
                        if isinstance(val, bool) and val:
                            return True, f"Available (available=true)"
                    if 'seats' in data:
                        try:
                            seats = int(data.get('seats',0))
                            if seats>0:
                                return True, f"Available (seats={seats})"
                        except Exception:
                            pass
                # fallback: stringify
                text = json.dumps(data)
            else:
                text = resp.text

            if keyword:
                if keyword.lower() in text.lower():
                    return True, f"Found keyword '{keyword}'"
            return False, "No match"
        except Exception as e:
            return False, f"Error: {e}"

    def run_loop(self):
        url = self.url_var.get().strip()
        keyword = self.keyword_var.get().strip()
        interval = int(self.interval_var.get())
        last_alert = False
        while self.running:
            ok, reason = self.check_once(url, keyword)
            self.log_msg(reason)
            if ok and not last_alert:
                msg = f"Ticket might be available: {url} -- {reason}"
                self.send_telegram(msg)
                # also show desktop alert
                try:
                    messagebox.showinfo("Ticket Watcher", msg)
                except Exception:
                    pass
                last_alert = True
            elif not ok:
                last_alert = False
            time.sleep(interval)

if __name__ == '__main__':
    root = tk.Tk()
    app = WatcherApp(root)
    root.mainloop()
