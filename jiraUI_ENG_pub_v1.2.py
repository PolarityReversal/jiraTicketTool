#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JIRA Ticket UI Tool

Features:
1. Get Latest 10 Tickets: After connecting to JIRA, click the "Get Latest 10 Tickets" button.
   The system uses a JQL filter to retrieve the latest tickets.
   The first click retrieves the newest 10 tickets, the second click retrieves the next 10, etc.
   When a ticket is selected from the list, a background thread fetches the ticket's title, description,
   and complete comment conversation while resolving @mentions.
   Each section header is displayed in bold with a larger font.
2. Search Tickets: Enter one or more ticket numbers (with any delimiter) in the "Search Ticket" field,
   then click the "Search" button to search for tickets by their numbers.
   After a search, the right panel will only display how many tickets were found.
3. open selected: Opens all selected tickets in your web browser.
4. lock selected: Toggles lock/unlock for selected tickets. Locked tickets display an asterisk,
   always appear above unlocked ones, and remain in the left panel across sessions.
5. export selected: Exports the selected tickets into a txt file, one per line (locked tickets show an asterisk).
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import re, threading, configparser, os, webbrowser, datetime
from jira import JIRA

CONFIG_FILE = "jira_config.ini"

def load_config():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        jira_url = config.get("JIRA", "url", fallback="")
        jira_user = config.get("JIRA", "user", fallback="")
        jira_token = config.get("JIRA", "token", fallback="")
    else:
        jira_url = ""
        jira_user = ""
        jira_token = ""
    return {"url": jira_url, "user": jira_user, "token": jira_token}

def save_config(url, user, token):
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    if not config.has_section("JIRA"):
        config.add_section("JIRA")
    config.set("JIRA", "url", url)
    config.set("JIRA", "user", user)
    config.set("JIRA", "token", token)
    with open(CONFIG_FILE, "w") as configfile:
        config.write(configfile)

def load_locked_tickets():
    config = configparser.ConfigParser()
    locked = set()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        if config.has_section("LOCKED") and config.has_option("LOCKED", "tickets"):
            tickets_str = config.get("LOCKED", "tickets")
            if tickets_str:
                locked = set(ticket.strip() for ticket in tickets_str.split(",") if ticket.strip())
    return locked

def save_locked_tickets(locked_set):
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    if not config.has_section("LOCKED"):
        config.add_section("LOCKED")
    config.set("LOCKED", "tickets", ",".join(sorted(locked_set)))
    with open(CONFIG_FILE, "w") as configfile:
        config.write(configfile)

user_cache = {}

def get_display_name(account_id, jira):
    if account_id in user_cache:
        return user_cache[account_id]
    try:
        user_obj = jira.user(account_id)
        name = getattr(user_obj, 'displayName', account_id)
        user_cache[account_id] = name
        return name
    except Exception:
        return "Unknown User"

def resolve_mentions(text, jira):
    if not text:
        return text
    return re.sub(r"\[~accountid:([^\]]+)\]", lambda m: "@" + get_display_name(m.group(1), jira), text)

def connect_jira(url, user, token):
    try:
        jira = JIRA(server=url, basic_auth=(user, token))
        return jira
    except Exception as e:
        messagebox.showerror("Connection Error", f"Unable to connect to JIRA: {e}")
        return None

def get_recent_tickets(jira, start_at=0, max_results=10):
    jql = 'ORDER BY created DESC'
    try:
        issues = jira.search_issues(jql, startAt=start_at, maxResults=max_results)
        return issues
    except Exception as e:
        messagebox.showerror("Error", f"Failed to retrieve tickets: {e}")
        return []

def get_ticket_conversation(jira, ticket_key):
    try:
        issue = jira.issue(ticket_key, expand='comment')
        comments = issue.fields.comment.comments if hasattr(issue.fields.comment, 'comments') else []
        sorted_comments = sorted(comments, key=lambda c: c.created)
        conv = ""
        for comment in sorted_comments:
            date = comment.created.split("T")[0]
            author = comment.author.displayName if hasattr(comment.author, "displayName") else comment.author.name
            body = comment.body.strip()
            body = resolve_mentions(body, jira)
            conv += f"{date} - {author} commented:\n{body}\n\n"
        return conv if conv else "No Comments"
    except Exception as e:
        return f"Failed to retrieve comments for Ticket {ticket_key}: {e}"

def search_tickets(jira, search_input):
    ticket_keys = re.findall(r'[A-Za-z]+-\d+', search_input)
    results = []
    for key in ticket_keys:
        try:
            issue = jira.issue(key)
            results.append(issue)
        except Exception:
            pass
    return results

class JiraUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JIRA Ticket UI Tool")
        self.geometry("900x700")
        self.current_page = 1
        self.tickets = []
        self.jira = None
        self.locked_tickets = load_locked_tickets()

        config_data = load_config()
        jira_url = config_data.get("url", "")
        jira_user = config_data.get("user", "")
        jira_token = config_data.get("token", "")

        cfg_frame = ttk.LabelFrame(self, text="JIRA Configuration")
        cfg_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(cfg_frame, text="JIRA URL:").grid(row=0, column=0, sticky="e", padx=5, pady=2)
        self.entry_url = ttk.Entry(cfg_frame, width=50)
        self.entry_url.grid(row=0, column=1, padx=5, pady=2)
        self.entry_url.insert(0, jira_url)

        ttk.Label(cfg_frame, text="User:").grid(row=1, column=0, sticky="e", padx=5, pady=2)
        self.entry_user = ttk.Entry(cfg_frame, width=50)
        self.entry_user.grid(row=1, column=1, padx=5, pady=2)
        self.entry_user.insert(0, jira_user)

        ttk.Label(cfg_frame, text="API Token:").grid(row=2, column=0, sticky="e", padx=5, pady=2)
        self.entry_token = ttk.Entry(cfg_frame, width=50, show="*")
        self.entry_token.grid(row=2, column=1, padx=5, pady=2)
        self.entry_token.insert(0, jira_token)

        self.save_token_var = tk.BooleanVar(value=True if jira_token else False)
        self.chk_save_token = ttk.Checkbutton(cfg_frame, text="Save API Token", variable=self.save_token_var)
        self.chk_save_token.grid(row=2, column=2, padx=5, pady=2)
        self.save_token_var.trace("w", self.update_lock_button_state)

        btn_frame = ttk.LabelFrame(self, text="Actions")
        btn_frame.pack(fill="x", padx=10, pady=5)

        self.btn_get_tickets = ttk.Button(btn_frame, text="Get Latest 10 Tickets", command=self.fetch_tickets)
        self.btn_get_tickets.grid(row=0, column=0, padx=5, pady=5)

        ttk.Label(btn_frame, text="Search Ticket:").grid(row=0, column=1, padx=5, pady=5)
        self.entry_search = ttk.Entry(btn_frame, width=30)
        self.entry_search.grid(row=0, column=2, padx=5, pady=5)

        self.btn_search = ttk.Button(btn_frame, text="Search", command=self.search_ticket_action)
        self.btn_search.grid(row=0, column=3, padx=5, pady=5)

        self.btn_open_selected = ttk.Button(btn_frame, text="open selected", command=self.open_selected_tickets)
        self.btn_open_selected.grid(row=0, column=4, padx=5, pady=5)

        self.btn_lock_selected = ttk.Button(btn_frame, text="lock selected", command=self.lock_selected_tickets)
        self.btn_lock_selected.grid(row=0, column=5, padx=5, pady=5)

        self.btn_export_selected = ttk.Button(btn_frame, text="export selected", command=self.export_selected_ticket_list)
        self.btn_export_selected.grid(row=0, column=6, padx=5, pady=5)

        content_frame = ttk.Frame(self)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.ticket_list = tk.Listbox(content_frame, width=20, selectmode=tk.EXTENDED)
        self.ticket_list.pack(side="left", fill="y", padx=(0, 5))
        self.ticket_list.bind("<<ListboxSelect>>", self.on_ticket_select)

        self.text_display = scrolledtext.ScrolledText(content_frame, wrap="word")
        self.text_display.pack(side="left", fill="both", expand=True)

        self.text_display.tag_configure("header", font=("Helvetica", 14, "bold"))
        self.text_display.tag_configure("normal", font=("Helvetica", 12))

        # On startup, ensure locked tickets remain in the list
        if self.locked_tickets:
            for key in self.locked_tickets:
                if not any(getattr(ticket, "key", "") == key for ticket in self.tickets):
                    Dummy = type("DummyTicket", (), {})
                    dummy = Dummy()
                    dummy.key = key
                    self.tickets.append(dummy)
            self.update_ticket_list_display()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def update_lock_button_state(self, *args):
        self.btn_lock_selected.config(state=tk.NORMAL)

    def update_ticket_list_display(self):
        def sort_key(ticket):
            try:
                prefix, num = ticket.key.split("-")
                num = int(num)
            except Exception:
                prefix = ticket.key
                num = 0
            locked_flag = 0 if ticket.key in self.locked_tickets else 1
            return (locked_flag, prefix, -num)
        sorted_tickets = sorted(self.tickets, key=sort_key)
        self.ticket_list.delete(0, tk.END)
        for ticket in sorted_tickets:
            display_key = ticket.key
            if ticket.key in self.locked_tickets and not display_key.endswith("*"):
                display_key += "*"
            self.ticket_list.insert(tk.END, display_key)

    def fetch_tickets(self):
        url = self.entry_url.get().strip()
        user = self.entry_user.get().strip()
        token = self.entry_token.get().strip()
        self.jira = connect_jira(url, user, token)
        if not self.jira:
            return

        start_at = (self.current_page - 1) * 10
        new_tickets = get_recent_tickets(self.jira, start_at=start_at, max_results=10)
        if self.current_page == 1:
            # Preserve already locked tickets
            locked_list = [ticket for ticket in self.tickets if getattr(ticket, "key", "") in self.locked_tickets]
            self.tickets = locked_list
        if new_tickets:
            existing_keys = set(getattr(ticket, "key", "") for ticket in self.tickets)
            for ticket in new_tickets:
                if ticket.key not in existing_keys:
                    self.tickets.append(ticket)
            self.current_page += 1
        else:
            messagebox.showinfo("Info", "No more tickets available.")
        self.update_ticket_list_display()

    def on_ticket_select(self, event):
        if not self.tickets:
            return
        selection = self.ticket_list.curselection()
        if not selection:
            return
        index = selection[0]
        ticket = self.tickets[index]
        # For locked tickets, force reconnection using current token (even if self.jira is set)
        if ticket.key in self.locked_tickets:
            url = self.entry_url.get().strip()
            user = self.entry_user.get().strip()
            token = self.entry_token.get().strip()
            self.jira = connect_jira(url, user, token)
            if not self.jira:
                messagebox.showerror("Error", f"Unable to connect to JIRA, cannot load ticket {ticket.key}")
                return
        # If ticket is a dummy (lacks full fields), reload it
        if not hasattr(ticket, "fields"):
            try:
                ticket = self.jira.issue(ticket.key)
                for i, t in enumerate(self.tickets):
                    if getattr(t, "key", "") == ticket.key:
                        self.tickets[i] = ticket
                        break
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load ticket {ticket.key}: {e}")
                return

        self.text_display.delete(1.0, tk.END)
        self.text_display.insert(tk.END, "Loading, please wait...", "normal")
        def fetch_details():
            ticket_id = ticket.key
            title = ticket.fields.summary
            description = ticket.fields.description if ticket.fields.description else "No Description"
            description = resolve_mentions(description, self.jira)
            conversation = get_ticket_conversation(self.jira, ticket.key)
            self.text_display.after(0, lambda: self.update_ticket_details(ticket_id, title, description, conversation))
        threading.Thread(target=fetch_details).start()

    def update_ticket_details(self, ticket_id, title, description, conversation):
        self.text_display.delete(1.0, tk.END)
        self.text_display.insert(tk.END, "Ticket\n", "header")
        self.text_display.insert(tk.END, f"{ticket_id}\n\n", "normal")
        self.text_display.insert(tk.END, "Title\n", "header")
        self.text_display.insert(tk.END, f"{title}\n\n", "normal")
        self.text_display.insert(tk.END, "Description\n", "header")
        self.text_display.insert(tk.END, f"{description}\n\n", "normal")
        self.text_display.insert(tk.END, "Full Comment Conversation\n", "header")
        self.text_display.insert(tk.END, conversation, "normal")

    def search_ticket_action(self):
        if not self.jira:
            url = self.entry_url.get().strip()
            user = self.entry_user.get().strip()
            token = self.entry_token.get().strip()
            self.jira = connect_jira(url, user, token)
            if not self.jira:
                return
        search_input = self.entry_search.get().strip()
        if not search_input:
            messagebox.showwarning("Warning", "Please enter ticket number(s) to search.")
            return
        results = search_tickets(self.jira, search_input)
        if not results:
            messagebox.showinfo("Info", "No tickets found matching the search criteria.")
            return
        # Merge search results with locked tickets so locked ones are preserved
        locked_dict = {ticket.key: ticket for ticket in self.tickets if getattr(ticket, "key", "") in self.locked_tickets}
        for ticket in results:
            locked_dict[ticket.key] = ticket
        merged = list(locked_dict.values())
        non_locked = [ticket for ticket in results if ticket.key not in self.locked_tickets]
        merged_keys = set(ticket.key for ticket in merged)
        for ticket in non_locked:
            if ticket.key not in merged_keys:
                merged.append(ticket)
        self.tickets = merged
        self.update_ticket_list_display()
        self.text_display.delete(1.0, tk.END)
        self.text_display.insert(tk.END, f"Found {len(self.tickets)} ticket(s).\n", "header")

    def open_selected_tickets(self):
        if not self.tickets:
            messagebox.showwarning("Warning", "No tickets available to open.")
            return
        selected_indices = self.ticket_list.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select at least one ticket to open.")
            return
        base_url = self.entry_url.get().strip().rstrip("/")
        for index in selected_indices:
            ticket_display = self.ticket_list.get(index)
            ticket_key = ticket_display.rstrip("*")
            ticket_url = f"{base_url}/browse/{ticket_key}"
            webbrowser.open_new_tab(ticket_url)

    def lock_selected_tickets(self):
        selected_indices = self.ticket_list.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select at least one ticket to lock/unlock.")
            return
        for index in selected_indices:
            ticket_display = self.ticket_list.get(index)
            ticket_key = ticket_display.rstrip("*")
            if ticket_key in self.locked_tickets:
                self.locked_tickets.remove(ticket_key)
            else:
                self.locked_tickets.add(ticket_key)
        self.update_ticket_list_display()

    def export_selected_ticket_list(self):
        selected_indices = self.ticket_list.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select at least one ticket to export.")
            return
        now = datetime.datetime.now()
        time_str = now.strftime("%H%M%S")
        date_str = now.strftime("%m-%d-%Y")
        num_tickets = len(selected_indices)
        filename = f"current-{time_str}_{date_str}_{num_tickets}_tickets.txt"
        lines = [self.ticket_list.get(index) for index in selected_indices]
        try:
            with open(filename, "w") as f:
                for line in lines:
                    f.write(line + "\n")
            messagebox.showinfo("Export", f"Exported selected tickets to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export ticket list: {e}")

    def on_closing(self):
        url = self.entry_url.get().strip()
        user = self.entry_user.get().strip()
        token = self.entry_token.get().strip() if self.save_token_var.get() else ""
        save_config(url, user, token)
        save_locked_tickets(self.locked_tickets)
        self.destroy()

if __name__ == "__main__":
    app = JiraUI()
    app.mainloop()
