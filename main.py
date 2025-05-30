import sqlite3
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
import re

class LoginWindow:
    def __init__(self, root, on_login):
        self.root = root
        self.on_login = on_login
        self.frame = tk.Frame(root)
        self.frame.pack(padx=20, pady=20)

        tk.Label(self.frame, text="Username:").grid(row=0, column=0)
        self.username_entry = tk.Entry(self.frame)
        self.username_entry.grid(row=0, column=1)

        tk.Label(self.frame, text="Password:").grid(row=1, column=0)
        self.password_entry = tk.Entry(self.frame, show="*")
        self.password_entry.grid(row=1, column=1)

        tk.Button(self.frame, text="Login", command=self.try_login).grid(row=2, columnspan=2, pady=10)

    def try_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()

        conn = sqlite3.connect("user_auth.db")
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT,
                permission TEXT
            )
        """)
        conn.commit()
        c.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO users (username, password, role, permission) VALUES (?, ?, ?, ?)",
                      ("admin", "admin123", "admin", "Full write"))
            conn.commit()

        c.execute("SELECT role, permission FROM users WHERE username = ? AND password = ?", (username, password))
        result = c.fetchone()
        conn.close()

        if result:
            role, permission = result
            self.frame.destroy()
            self.on_login(username, role, permission)
        else:
            messagebox.showerror("Login Failed", "Invalid username or password")

class DatabaseTemplates:
    @staticmethod
    def create_user_db(cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS data (id INTEGER PRIMARY KEY, address TEXT, email TEXT)")

    @staticmethod
    def create_business_db(cursor):
        cursor.execute("CREATE TABLE IF NOT EXISTS Customers (id INTEGER PRIMARY KEY, name TEXT, [order] TEXT, [previous orders] TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS Warehouse (id INTEGER PRIMARY KEY, item TEXT, stock INTEGER, price REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS Shop (id INTEGER PRIMARY KEY, item TEXT, customer TEXT, price REAL)")

class PermissionManager:
    def __init__(self, current_user, current_role):
        self.user = current_user
        self.role = current_role

    def can_change_permissions(self, db_permission):
        return self.role == "admin" or db_permission == "Full write"

    def has_write_access(self, db_permission):
        return db_permission in ["Write", "Full write"]

    def has_read_access(self, db_permission):
        return db_permission in ["Read-only", "Write", "Full write"]

    def is_blocked(self, db_permission):
        return db_permission == "Closed"

class SQLEditor:
    def __init__(self, root, username, role, permission):
        self.root = root
        self.root.title("OpenDoc SQL")
        self.conn = sqlite3.connect('example.db')
        self.cursor = self.conn.cursor()
        self.table_list = {}
        self.username = username
        self.role = role
        self.permission = permission
        self.perm_mgr = PermissionManager(username, role)
        self.conn = None
        self.cursor = None
        self.setup_gui()

        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")

        tables = self.cursor.fetchall()

        for table in tables:
            self.table_list[table[0]] = None


        self.sort_column = None
        self.sort_ascending = True

        self.setup_gui()
        self.load_db_structure()

    def setup_gui(self):
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="New", accelerator="Ctrl+N", command=self.new_file)
        file_menu.add_command(label="Open", accelerator="Ctrl+O", command=self.open_file)
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_file)
        file_menu.add_command(label="Save As", accelerator="Ctrl+Shift+S", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu_bar, tearoff=0)
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Y")
        table_menu = tk.Menu(edit_menu, tearoff=0)
        table_menu.add_command(label="New Table", command=self.new_table)
        table_menu.add_command(label="Delete Table", command=self.delete_table)
        column_menu = tk.Menu(table_menu, tearoff=0)
        column_menu.add_command(label="Add Column", command=self.add_column)
        column_menu.add_command(label="Delete Column", command=self.delete_column)
        column_menu.add_command(label="Rename Column", command=self.rename_column)
        table_menu.add_cascade(label="Columns", menu=column_menu)
        edit_menu.add_cascade(label="Table", menu=table_menu)
        row_menu = tk.Menu(edit_menu, tearoff=0)
        row_menu.add_command(label="Add Rows", command=self.add_rows)
        row_menu.add_command(label="Add Empty", command=self.add_empty_rows)
        row_menu.add_command(label="Delete Rows", command=self.delete_rows)
        edit_menu.add_cascade(label="Rows", menu=row_menu)
        menu_bar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Edit Column", command=self.edit_column)

        self.root.config(menu=menu_bar)

        self.root.bind_all("<Control-o>", lambda e: self.open_file())
        self.root.bind_all("<Control-s>", lambda e: self.save_file())
        self.root.bind_all("<Control-S>", lambda e: self.save_file_as())
        self.root.bind_all("<Control-n>", lambda e: self.new_file())
        self.root.bind_all("<Control-z>", lambda e: None)
        self.root.bind_all("<Control-y>", lambda e: None)
        self.root.bind_all("<Delete>", lambda e: self.delete_rows)

        self.main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        self.tree_frame = tk.Frame(self.main_pane)
        self.db_tree = ttk.Treeview(self.tree_frame)
        self.db_tree.pack(fill=tk.BOTH, expand=True)
        self.db_tree.bind('<<TreeviewSelect>>', self.on_table_select)
        self.main_pane.add(self.tree_frame, width=200)

        self.table_frame = tk.Frame(self.main_pane)
        self.table = ttk.Treeview(self.table_frame, show="headings")
        self.table.pack(fill=tk.BOTH, expand=True)
        self.table.bind("<Button-1>", self.on_column_click)
        self.table.bind("<Double-1>", self.edit_cell)
        self.main_pane.add(self.table_frame, width=800)

        # Right: SQL Console
        self.right_frame = tk.Frame(self.main_pane)
        self.sql_entry = ScrolledText(self.right_frame, height=10, width=30, wrap=tk.WORD)
        self.sql_entry.pack(fill=tk.X)
        self.sql_entry.bind("<KeyRelease>", self.syntax_highlight)
        tk.Button(self.right_frame, text="Execute SQL", command=self.execute_sql).pack()

        self.main_pane.add(self.right_frame, width=300)

    def load_db_structure(self):
        self.db_tree.delete(*self.db_tree.get_children())
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for table_name in self.cursor.fetchall():
            self.db_tree.insert('', 'end', text=table_name[0], values=(table_name[0],))

    def on_table_select(self, event):
        selected = self.db_tree.focus()
        table_name = self.db_tree.item(selected)['text']
        self.show_table_data(table_name)

    def show_table_data(self, table_name):
        self.current_table = table_name
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [info[1] for info in self.cursor.fetchall()]
        self.table.delete(*self.table.get_children())
        self.table['columns'] = columns

        for col in columns:
            self.table.heading(col, text=col)

        sql = f"SELECT * FROM {table_name}"
        if hasattr(self, 'limit'):
            sql += f" LIMIT {self.limit}"
        self.cursor.execute(sql)
        rows = self.cursor.fetchall()

        for row in rows:
            self.table.insert('', 'end', values=row)

    def on_column_click(self, event):
        region = self.table.identify("region", event.x, event.y)
        if region != "heading":
            return
        column = self.table.identify_column(event.x)
        column_id = int(column.replace("#", "")) - 1
        column_name = self.table['columns'][column_id]

        self.sort_ascending = not self.sort_ascending if self.sort_column == column_name else True
        self.sort_column = column_name

        order = 'ASC' if self.sort_ascending else 'DESC'
        sql = f"SELECT * FROM {self.current_table} ORDER BY {column_name} {order}"
        if hasattr(self, 'limit'):
            sql += f" LIMIT {self.limit}"

        self.cursor.execute(sql)
        rows = self.cursor.fetchall()

        self.table.delete(*self.table.get_children())
        for row in rows:
            self.table.insert('', 'end', values=row)

    def edit_cell(self, event):
        region = self.table.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = self.table.identify_row(event.y)
        col_id = self.table.identify_column(event.x)
        col_index = int(col_id.replace("#", "")) - 1
        col_name = self.table['columns'][col_index]
        old_value = self.table.item(row_id)['values'][col_index]

        new_value = simpledialog.askstring("Edit Cell", f"New value for {col_name}:", initialvalue=old_value)
        if new_value is not None:
            values = self.table.item(row_id)['values']
            primary_key_col = self.table['columns'][0]
            primary_key_val = values[0]
            values[col_index] = new_value
            try:
                self.cursor.execute(f"UPDATE {self.current_table} SET {col_name} = ? WHERE {primary_key_col} = ?", (new_value, primary_key_val))
                self.conn.commit()
                self.show_table_data(self.current_table)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def add_empty_rows(self):
        if not hasattr(self, 'current_table'):
            return
        try:
            n = simpledialog.askinteger("Add Empty Rows", "How many empty rows?")
            if n:
                self.cursor.execute(f"PRAGMA table_info({self.current_table})")
                columns = [info[1] for info in self.cursor.fetchall() if info[5] == 0]
                placeholders = ','.join(['NULL'] * len(columns))
                for _ in range(n):
                    self.cursor.execute(f"INSERT INTO {self.current_table} ({','.join(columns)}) VALUES ({placeholders})")
                self.conn.commit()
                self.show_table_data(self.current_table)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def add_column(self):
        if not hasattr(self, 'current_table'):
            return
        name = simpledialog.askstring("Add Column", "Column name:")
        dtype = simpledialog.askstring("Add Column", "Data type:")
        if name and dtype:
            try:
                self.cursor.execute(f"ALTER TABLE {self.current_table} ADD COLUMN {name} {dtype}")
                self.conn.commit()
                self.show_table_data(self.current_table)
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def delete_column(self):
        messagebox.showinfo("Notice", "SQLite does not support deleting columns directly. Use SQL script manually.")

    def rename_column(self):
        messagebox.showinfo("Notice", "SQLite does not support renaming columns directly. Use SQL script manually.")

    def execute_sql(self):
        sql = self.sql_entry.get("1.0", tk.END).strip()
        try:
            self.cursor.executescript(sql)
            self.conn.commit()
            self.load_db_structure()
            if hasattr(self, 'current_table'):
                self.show_table_data(self.current_table)
            messagebox.showinfo("Success", "SQL executed successfully.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def syntax_highlight(self, event=None):
        self.sql_entry.tag_remove("keyword", "1.0", tk.END)
        self.sql_entry.tag_remove("type", "1.0", tk.END)
        self.sql_entry.tag_remove("control", "1.0", tk.END)

        content = self.sql_entry.get("1.0", tk.END)

        keyword_pattern = r"\\b(SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|DROP|ORDER|BY|ASC|DESC|LIMIT|PRIMARY|KEY)\\b"
        type_pattern = r"\\b(INTEGER|TEXT|REAL|BLOB|NUMERIC)\\b"
        control_pattern = r"\\b(IF|ELSE|BEGIN|END)\\b"

        for match in re.finditer(keyword_pattern, content, re.IGNORECASE):
            self.sql_entry.tag_add("keyword", f"1.0+{match.start()}c", f"1.0+{match.end()}c")
        for match in re.finditer(type_pattern, content, re.IGNORECASE):
            self.sql_entry.tag_add("type", f"1.0+{match.start()}c", f"1.0+{match.end()}c")
        for match in re.finditer(control_pattern, content, re.IGNORECASE):
            self.sql_entry.tag_add("control", f"1.0+{match.start()}c", f"1.0+{match.end()}c")

        self.sql_entry.tag_config("keyword", foreground="blue", font=("Consolas", 10, "bold"))
        self.sql_entry.tag_config("type", foreground="green")
        self.sql_entry.tag_config("control", foreground="orange")

    def open_file(self):
        if self.perm_mgr.is_blocked(self.permission):
            messagebox.showwarning("Access Denied", "You do not have permission to open databases.")
            return

        path = filedialog.askopenfilename(title="Open Database", filetypes=[("SQLite DB", "*.db")])
        if path:
            try:
                self.conn = sqlite3.connect(path)
                self.cursor = self.conn.cursor()
                messagebox.showinfo("Opened", f"Opened {path}")
            except Exception as e:
                messagebox.showerror("Error", str(e))


    def save_file(self):
        if hasattr(self, 'db_path') and self.db_path:
            self.conn.commit()
            messagebox.showinfo("Saved", f"Database saved to {self.db_path}")
        else:
            self.save_file_as()

    def save_file_as(self):
        path = filedialog.asksaveasfilename(title="Save Database As", defaultextension=".db",
                                            filetypes=[("SQLite Database", "*.db")])
        if path:
            try:
                self.conn.commit()
                self.conn.close()
                import shutil
                shutil.copy(self.db_path if hasattr(self, 'db_path') else 'example.db', path)
                self.conn = sqlite3.connect(path)
                self.cursor = self.conn.cursor()
                self.db_path = path
                self.load_db_structure()
                messagebox.showinfo("Saved As", f"Database saved as {path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save database: {str(e)}")

    def new_file(self):
        path = filedialog.asksaveasfilename(title="Create New Database", defaultextension=".db", filetypes=[("SQLite DB", "*.db")])
        if path:
            self.conn = sqlite3.connect(path)
            self.cursor = self.conn.cursor()
            win = tk.Toplevel(self.root)
            win.title("Choose Template")
            tk.Button(win, text="Create User Database", command=lambda: self.create_template(win, 'user')).pack(pady=5)
            tk.Button(win, text="Create Business Database", command=lambda: self.create_template(win, 'business')).pack(pady=5)

    def create_template(self, window, template):
        if template == 'user':
            DatabaseTemplates.create_user_db(self.cursor)
        elif template == 'business':
            DatabaseTemplates.create_business_db(self.cursor)
        self.conn.commit()
        window.destroy()
        messagebox.showinfo("Template Created", f"{template.capitalize()} database created successfully.")

    def new_table(self):
        name = simpledialog.askstring("New Table", "Table name:")
        if name:
            columns = simpledialog.askstring("New Table", "Columns (e.g., id INTEGER PRIMARY KEY, name TEXT):")
            if columns:
                try:
                    self.cursor.execute(f"CREATE TABLE {name} ({columns})")
                    self.conn.commit()
                    self.load_db_structure()
                except Exception as e:
                    messagebox.showerror("Error", str(e))

    def delete_table(self):
        if hasattr(self, 'current_table'):
            try:
                self.cursor.execute(f"DROP TABLE {self.current_table}")
                self.conn.commit()
                self.load_db_structure()
                self.table.delete(*self.table.get_children())
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def add_rows(self):
        if not hasattr(self, 'current_table'):
            return
        self.cursor.execute(f"PRAGMA table_info({self.current_table})")
        columns = [info[1] for info in self.cursor.fetchall() if info[5] == 0]
        values = []
        for col in columns:
            val = simpledialog.askstring("Insert Row", f"Value for {col}:")
            values.append(val)
        placeholders = ','.join(['?'] * len(values))
        try:
            self.cursor.execute(f"INSERT INTO {self.current_table} ({','.join(columns)}) VALUES ({placeholders})", values)
            self.conn.commit()
            self.show_table_data(self.current_table)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete_rows(self):
        selected_items = self.table.selection()
        if not selected_items:
            return
        for item in selected_items:
            values = self.table.item(item)['values']
            conditions = " AND ".join([f"{col} = ?" for col in self.table['columns']])
            try:
                self.cursor.execute(f"DELETE FROM {self.current_table} WHERE {conditions}", values)
                self.conn.commit()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        self.show_table_data(self.current_table)

    def edit_column(self):
        column = simpledialog.askstring("Edit Column", "Enter column name to edit:")
        if not column:
            return
        new_value = simpledialog.askstring("Edit Column", f"Enter new value for all rows in '{column}':")
        if new_value is None:
            return
        table_name = self.table_list.get()
        self.cursor.execute(f"UPDATE {table_name} SET {column} = ?", (new_value,))
        self.conn.commit()
        self.show_table_data()

    def copy_row(self):
        selected = self.table.selection()
        if not selected:
            return
        self.copied_row = self.table.item(selected[0])['values']

    def paste_row(self):
        if not self.copied_row:
            return
        table_name = self.table_list.get()
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [info[1] for info in self.cursor.fetchall()]

        id_col = columns[0]  # assume ID is first
        new_id = simpledialog.askinteger("Paste Row", f"Enter new {id_col} value:")
        if new_id is None:
            return

        # shift IDs up
        self.cursor.execute(f"UPDATE {table_name} SET {id_col} = {id_col} + 1 WHERE {id_col} >= ? ORDER BY {id_col} DESC", (new_id,))
        self.conn.commit()

        new_row = self.copied_row[:]
        new_row[0] = new_id

        placeholders = ', '.join('?' for _ in columns)
        self.cursor.execute(f"INSERT INTO {table_name} VALUES ({placeholders})", new_row)
        self.conn.commit()
        self.show_table_data()

    def find_in_column(self):
        column = simpledialog.askstring("Find", "Find in column: ")
        value = simpledialog.askstring("Find", f"Search in column '{column}':")
        if value is None:
            return
        table_name = self.table_list.get()
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        col_types = {info[1]: info[2].upper() for info in self.cursor.fetchall()}

        if 'CHAR' in col_types[column] or 'TEXT' in col_types[column]:
            query = f"SELECT * FROM {table_name} WHERE {column} LIKE ?"
            param = f"%{value}%"
        else:
            query = f"SELECT * FROM {table_name} WHERE {column} = ?"
            param = value

        self.cursor.execute(query, (param,))
        rows = self.cursor.fetchall()

        self.table.delete(*self.table.get_children())
        for row in rows:
            self.table.insert("", tk.END, values=row)


if __name__ == '__main__':
    def start_app(username, role, permission):
        SQLEditor(login_root, username, role, permission)

    global login_root
    login_root = tk.Tk()
    LoginWindow(login_root, start_app)
    login_root.mainloop()


