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
3. Open Selected Ticket(s): Click this button to open all selected tickets from the left list in your web browser.
   The ticket URL is constructed using the provided JIRA URL.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import re, threading, configparser, os, webbrowser
from jira import JIRA

CONFIG_FILE = "jira_config.ini"

# ---------------------------
# Configuration Functions
# ---------------------------
def load_config():
    """
    Load JIRA configuration from the config file.
    Returns a dictionary with keys 'url', 'user', and 'token'. Defaults to empty strings if not found.
    """
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
    """
    Save JIRA URL, User, and (optionally) API Token to the config file.
    The API Token is only saved if token is non-empty.
    """
    config = configparser.ConfigParser()
    config["JIRA"] = {"url": url, "user": user, "token": token}
    with open(CONFIG_FILE, "w") as configfile:
        config.write(configfile)

# ---------------------------
# User Info Cache and @-Processing Functions
# ---------------------------
user_cache = {}

def get_display_name(account_id, jira):
    """
    Get the user's display name based on account_id.
    Returns 'Unknown User' on failure.
    """
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
    """
    Replace markers like [~accountid:xxx] in the text with the actual display name (e.g., @RealName),
    fixing issues where @mentions appear as user IDs.
    """
    if not text:
        return text
    return re.sub(r"\[~accountid:([^\]]+)\]", lambda m: "@" + get_display_name(m.group(1), jira), text)

# ---------------------------
# JIRA Connection and Ticket Retrieval Helper Functions
# ---------------------------
def connect_jira(url, user, token):
    """
    Connect to JIRA using the given URL, username, and API Token.
    Displays an error message if connection fails.
    """
    try:
        jira = JIRA(server=url, basic_auth=(user, token))
        return jira
    except Exception as e:
        messagebox.showerror("Connection Error", f"Unable to connect to JIRA: {e}")
        return None

def get_recent_tickets(jira, start_at=0, max_results=10):
    """
    Retrieve the most recent tickets, sorted by creation time in descending order.
    Supports pagination using startAt and maxResults.
    """
    jql = 'ORDER BY created DESC'
    try:
        issues = jira.search_issues(jql, startAt=start_at, maxResults=max_results)
        return issues
    except Exception as e:
        messagebox.showerror("Error", f"Failed to retrieve tickets: {e}")
        return []

def get_ticket_conversation(jira, ticket_key):
    """
    Retrieve the ticket's comment conversation, sorted by creation time in ascending order,
    and fix the @mention formatting.
    """
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
    """
    Extract ticket numbers from the input text and return the corresponding ticket objects.
    """
    ticket_keys = re.findall(r'[A-Za-z]+-\d+', search_input)
    results = []
    for key in ticket_keys:
        try:
            issue = jira.issue(key)
            results.append(issue)
        except Exception:
            pass
    return results

# ---------------------------
# Main UI Window
# ---------------------------
class JiraUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JIRA Ticket Tool")
        self.geometry("900x700")
        self.current_page = 1  # Current page for pagination (10 tickets per page)
        self.tickets = []
        self.jira = None

        # Load saved configuration (JIRA URL, User, and API Token if saved)
        config = load_config()
        jira_url = config.get("url", "")
        jira_user = config.get("user", "")
        jira_token = config.get("token", "")

        # JIRA Configuration Section
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

        # Checkbox to save API Token on exit
        self.save_token_var = tk.BooleanVar(value=True if jira_token else False)
        self.chk_save_token = ttk.Checkbutton(cfg_frame, text="Save API Token", variable=self.save_token_var)
        self.chk_save_token.grid(row=2, column=2, padx=5, pady=2)

        # Function Buttons Section
        btn_frame = ttk.LabelFrame(self, text="Actions")
        btn_frame.pack(fill="x", padx=10, pady=5)

        self.btn_get_tickets = ttk.Button(btn_frame, text="Get Latest 10 Tickets", command=self.fetch_tickets)
        self.btn_get_tickets.grid(row=0, column=0, padx=5, pady=5)

        ttk.Label(btn_frame, text="Search Ticket:").grid(row=0, column=1, padx=5, pady=5)
        self.entry_search = ttk.Entry(btn_frame, width=30)
        self.entry_search.grid(row=0, column=2, padx=5, pady=5)
        self.btn_search = ttk.Button(btn_frame, text="Search", command=self.search_ticket_action)
        self.btn_search.grid(row=0, column=3, padx=5, pady=5)

        self.btn_open_selected = ttk.Button(btn_frame, text="Open Selected Ticket(s)", command=self.open_selected_tickets)
        self.btn_open_selected.grid(row=0, column=4, padx=5, pady=5)

        # Display Section: Left list shows ticket numbers; right text box displays details.
        content_frame = ttk.Frame(self)
        content_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.ticket_list = tk.Listbox(content_frame, width=20, selectmode=tk.EXTENDED)
        self.ticket_list.pack(side="left", fill="y", padx=(0, 5))
        self.ticket_list.bind("<<ListboxSelect>>", self.on_ticket_select)

        self.text_display = scrolledtext.ScrolledText(content_frame, wrap="word")
        self.text_display.pack(side="left", fill="both", expand=True)

        # Configure text tags
        self.text_display.tag_configure("header", font=("Helvetica", 14, "bold"))
        self.text_display.tag_configure("normal", font=("Helvetica", 12))

        # Bind the window close event to save configuration
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def fetch_tickets(self):
        """
        Connect to JIRA and retrieve tickets in pages (10 tickets per page).
        """
        url = self.entry_url.get().strip()
        user = self.entry_user.get().strip()
        token = self.entry_token.get().strip()
        self.jira = connect_jira(url, user, token)
        if not self.jira:
            return

        start_at = (self.current_page - 1) * 10
        new_tickets = get_recent_tickets(self.jira, start_at=start_at, max_results=10)
        if self.current_page == 1:
            self.ticket_list.delete(0, tk.END)
            self.text_display.delete(1.0, tk.END)
            self.tickets = []
        if not new_tickets:
            messagebox.showinfo("Info", "No more tickets available.")
            return
        self.tickets.extend(new_tickets)
        for ticket in new_tickets:
            self.ticket_list.insert(tk.END, ticket.key)
        self.text_display.insert(tk.END, f"Page {self.current_page} retrieved, {len(new_tickets)} tickets loaded.\n", "normal")
        self.current_page += 1

    def on_ticket_select(self, event):
        """
        When a ticket is selected from the list, retrieve its details (title, description, all comments)
        in a background thread and update the UI.
        """
        if not self.tickets:
            return
        selection = self.ticket_list.curselection()
        if not selection:
            return
        index = selection[0]
        ticket = self.tickets[index]
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
        """
        Update the text display with the ticket's details, formatting headers in bold and large font.
        """
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
        """
        Search for tickets by the provided ticket number(s) and update the UI.
        After the search, only display in the text area the number of tickets found.
        """
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
        self.tickets = results
        self.ticket_list.delete(0, tk.END)
        for ticket in self.tickets:
            self.ticket_list.insert(tk.END, ticket.key)
        self.text_display.delete(1.0, tk.END)
        self.text_display.insert(tk.END, f"Found {len(self.tickets)} ticket(s).\n", "header")

    def open_selected_tickets(self):
        """
        Open the selected ticket(s) from the left list in the web browser.
        The ticket URL is constructed as: [JIRA URL]/browse/[ticket key].
        """
        if not self.tickets:
            messagebox.showwarning("Warning", "No tickets available to open.")
            return
        selected_indices = self.ticket_list.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select at least one ticket to open.")
            return
        base_url = self.entry_url.get().strip().rstrip("/")
        for index in selected_indices:
            ticket = self.tickets[index]
            ticket_url = f"{base_url}/browse/{ticket.key}"
            webbrowser.open_new_tab(ticket_url)

    def on_closing(self):
        """
        Save the current JIRA URL, User, and (optionally) API Token to the configuration file before closing.
        If the 'Save API Token' checkbox is not checked, the token is cleared.
        """
        url = self.entry_url.get().strip()
        user = self.entry_user.get().strip()
        token = self.entry_token.get().strip() if self.save_token_var.get() else ""
        save_config(url, user, token)
        self.destroy()

if __name__ == "__main__":
    app = JiraUI()
    app.mainloop()
