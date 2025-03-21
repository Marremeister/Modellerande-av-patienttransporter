import tkinter as tk
from tkinter import ttk


class ScrollableTable:
    def __init__(self, df):
        self.df = df

    def show(self):
        root = tk.Tk()
        root.title("Route Transport Times")

        # Create a frame for the Treeview widget
        frame = ttk.Frame(root)
        frame.pack(fill='both', expand=True)

        # Create the Treeview widget with columns from the DataFrame
        columns = list(self.df.columns)
        tree = ttk.Treeview(frame, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150, anchor="center")

        # Insert DataFrame rows into the Treeview
        for _, row in self.df.iterrows():
            tree.insert("", "end", values=list(row))

        # Add a vertical scrollbar
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        root.mainloop()
