"""
gui_app.py - PropManager Pro (Final Merged Version)
Sidebar navigation + complete SRS functionality.
"""

import os
import subprocess
from sys import platform
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from datetime import datetime, timedelta

from database import DatabaseManager
from invoice_engine import InvoiceEngine

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class PropManagerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.db = DatabaseManager(self.app_dir)
        self.invoice_engine = InvoiceEngine(self.db)
        self.all_tenants = self.db.get_all_active_tenants()

        self.title("PropManager Pro - Enterprise Control Panel")
        self.geometry("1100x680")
        self.minsize(1000, 600)

        # Main grid: sidebar + workspace
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ---- Sidebar ----
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(self.sidebar, text="PropManager Pro", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=20)

        ctk.CTkButton(self.sidebar, text="Dashboard", command=self.show_dashboard).grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Tenants", command=self.show_tenants).grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Onboarding", command=self.show_onboarding).grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Utilities & Ledger", command=self.show_utilities).grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Archive", command=self.show_archive).grid(row=5, column=0, padx=20, pady=10, sticky="ew")

        ctk.CTkLabel(self.sidebar, text="v2.2.0-Final", font=ctk.CTkFont(size=10)).grid(row=7, column=0, padx=20, pady=10)

        # ---- Workspace frames ----
        self.dashboard_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.tenants_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        # Tell self.tenants_frame how to distribute space to its row 0 and column 0
        self.tenants_frame.grid_columnconfigure(0, weight=1)
        self.tenants_frame.grid_rowconfigure(0, weight=1)

        self.onboard_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        # Tell self.onboard_frame how to distribute space to its row 0 and column 0
        self.onboard_frame.grid_columnconfigure(0, weight=1)
        self.onboard_frame.grid_rowconfigure(0, weight=1)

        self.util_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.archive_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")

        self._build_dashboard()
        
        self._build_onboarding()
        self._build_utilities()
        self._build_archive()

        self.show_dashboard()

    def _clear_workspace(self):
        for frame in (self.dashboard_frame, self.tenants_frame, self.onboard_frame, self.util_frame, self.archive_frame):
            frame.grid_forget()

    def show_dashboard(self):
        self._clear_workspace()
        self.dashboard_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self._refresh_dashboard()

    def show_tenants(self):
        self._clear_workspace()
        self.tenants_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self._build_tenants()

    def show_onboarding(self):
        self._clear_workspace()
        self.onboard_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

    def show_utilities(self):
        self._clear_workspace()
        self.util_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self._refresh_tenant_dropdowns()

    def show_archive(self):
        self._clear_workspace()
        self.archive_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self._refresh_moveout_dropdown()

    # -----------------------------------------------------------------
    # DASHBOARD
    # -----------------------------------------------------------------
    def _build_dashboard(self):
        self.dashboard_frame.grid_columnconfigure((0,1), weight=1)
        # Allow the row containing the textbox to expand
        self.dashboard_frame.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(self.dashboard_frame, text="System Overview", font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="w")

        self.card_active = ctk.CTkLabel(self.dashboard_frame, text="Active Units: --", font=ctk.CTkFont(size=16), fg_color="#1f2c3f", height=80, corner_radius=8)
        self.card_active.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        self.card_arb = ctk.CTkLabel(self.dashboard_frame, text="Arbitrage Earnings:\nElec: -- | Water: --", font=ctk.CTkFont(size=16), fg_color="#1f2c3f", height=80, corner_radius=8)
        self.card_arb.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # Search bar with live filtering
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_change) # Calls function on every keystroke
        
        self.search_bar = ctk.CTkEntry(self.dashboard_frame, placeholder_text="Search units...", textvariable=self.search_var)
        self.search_bar.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        

        ctk.CTkLabel(self.dashboard_frame, text="Active Units", font=ctk.CTkFont(size=14, weight="bold")).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.dash_text = ctk.CTkTextbox(self.dashboard_frame, height=360, activate_scrollbars=True)
        self.dash_text.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        
        # Initial data load
        self.update_textbox_display(self.all_tenants)

    def _on_search_change(self, *args):
        query = self.search_var.get().strip().lower()
        if not query:
            self.update_textbox_display(self.all_tenants)
            return
        filtered = [u for u in self.all_tenants if query in u['unit_id'].lower() or query in u['tenant_name'].lower()]
        self.update_textbox_display(filtered)
    
    def update_textbox_display(self, units):
        self.dash_text.configure(state="normal")
        self.dash_text.delete("1.0", tk.END)
        for u in units:
            bal = self.db.get_current_balance(u['unit_id'])
            self.dash_text.insert(tk.END, f"Unit {u['unit_id']:<6} | {u['tenant_name']:<25} | Balance: ₹{bal:,.2f}\n")
        self.dash_text.configure(state="disabled")

    def _refresh_dashboard(self):
        tenants = self.db.get_all_active_tenants()
        self.card_active.configure(text=f"Active Managed Units: {len(tenants)}")
        metrics = self.db.get_utility_arbitrage_metrics()
        self.card_arb.configure(text=f"Arbitrage Net Yield:\nElectricity: ₹{metrics['Electricity']:,.2f} | Water: ₹{metrics['Water']:,.2f}")

        self.dash_text.configure(state="normal")
        self.dash_text.delete("1.0", tk.END)
        for t in tenants:
            bal = self.db.get_current_balance(t['unit_id'])
            self.dash_text.insert(tk.END, f"Unit {t['unit_id']:<6} | {t['tenant_name']:<25} | Balance: ₹{bal:,.2f}\n")
        self.dash_text.configure(state="disabled")

    #-----------------------------------------------------------------
    # TENANTS (List + Search) - Placeholder for future expansion
    #-----------------------------------------------------------------

    def _build_tenants(self):
        scroll = ctk.CTkScrollableFrame(self.tenants_frame, width=750, height=580)
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        #scroll.grid_columnconfigure((0,1), weight=1)  # Add this line back if you want the main content to stretch, but for now we want it fixed size with a scrollbar on the right

        # Scroll bar is fixed to the right no matter what # when you add the upper line delete this so that the content stays fixed.
        scroll.grid_columnconfigure(0, weight=0)  # Main content (stays fixed size)
        scroll.grid_columnconfigure(4, weight=1)  # Right spacer

        ctk.CTkLabel(scroll, text="Tenant Updation", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=15, sticky="w")

        self.onb_entries = {}
        fields = [
            ("unit_id", "Unit ID"),
            ("tenant_name", "Full Legal Name"),
            ("phone", "Phone"),
            ("email", "Email"),
            ("permanent_address", "Permanent Address"),
            ("govt_id_type", "Govt ID Type (Aadhaar/PAN)"),
            ("govt_id_number", "Govt ID Number"),
            ("base_rent", "Base Monthly Rent (₹)"),
            ("security_deposit_held", "Security Deposit (₹)"),
            ("parent_1_name", "Parent 1 Name"),
            ("parent_1_phone", "Parent 1 Phone"),
            ("parent_2_name", "Parent 2 Name"),
            ("parent_2_phone", "Parent 2 Phone"),
            ("organization_or_college", "Organization/College"),
            ("designation_or_course", "Designation/Course"),
            ("required_notice_days", "Required Notice Days"),
            ("onboarding_date", "Onboarding Date (YYYY-MM-DD)"),
            ("water_fixed_charge", "Water Fixed Charge (₹)")
        ]
        for i, (key, label) in enumerate(fields):
            row = (i // 2) + 1
            col = i % 2
            ctk.CTkLabel(scroll, text=label).grid(row=row, column=col*2, padx=5, pady=4, sticky="e")
            entry = ctk.CTkEntry(scroll, width=200)
            entry.grid(row=row, column=col*2+1, padx=5, pady=4, sticky="w")
            self.onb_entries[key] = entry
            if key == "onboarding_date":
                entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

        row_after = (len(fields)//2) + 2
        ctk.CTkLabel(scroll, text="Profession").grid(row=row_after, column=0, padx=5, pady=4, sticky="e")
        self.profession_combo = ctk.CTkOptionMenu(scroll, values=["Student", "Working Professional", "Government", "Private", "Other"])
        self.profession_combo.grid(row=row_after, column=1, padx=5, pady=4, sticky="w")

        ctk.CTkLabel(scroll, text="Penalty Type").grid(row=row_after, column=2, padx=5, pady=4, sticky="e")
        self.penalty_combo = ctk.CTkOptionMenu(scroll, values=["Forfeit Full Security", "Fixed Charge 5000", "Fixed Charge 10000"])
        self.penalty_combo.grid(row=row_after, column=3, padx=5, pady=4, sticky="w")

        '''
        ctk.CTkLabel(scroll, text="Brokerage Fee (₹)").grid(row=row_after+1, column=0, padx=5, pady=4, sticky="e")
        self.brokerage_entry = ctk.CTkEntry(scroll, width=200)
        self.brokerage_entry.grid(row=row_after+1, column=1, padx=5, pady=4, sticky="w")
        self.brokerage_entry.insert(0, "0")
        '''

        self.agreement_path = tk.StringVar()
        self.pdf_status = ctk.CTkLabel(scroll, text="No PDF attached", text_color="gray")
        self.pdf_status.grid(row=row_after+2, column=0, columnspan=2, padx=10, pady=5, sticky="w")
        self.pdf_action_btn = ctk.CTkButton(scroll, text="View Agreement", command=self._open_pdf)
        self.pdf_action_btn.grid(row=row_after+2, column=2, columnspan=2, padx=10, pady=5, sticky="ew")

        # --- NEW: Added a Fetch/Pull Data Button ---
        ctk.CTkButton(
            scroll, 
            text="Fetch Data", 
            fg_color="#2b733e",
            height=45,
            command= lambda: [self._load_tenant_to_ui(), self._check_and_update_pdf_button()]  # Calls the data loading function, then checks PDF status
        ).grid(row=row_after+3, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # --- MODIFIED: Adjusted Submit Button to route to your update pipeline ---
        ctk.CTkButton(
            scroll, 
            text="Update Details", 
            fg_color="#2b733e", 
            height=45, 
            command=self._update_tenant_submit
        ).grid(row=row_after+3, column=2, columnspan=2, padx=10, pady=10, sticky="ew")

        # Master Unlock Button
        self.unlock_btn = ctk.CTkButton(
            scroll, 
            text= "Unlock Form for Editing (Requires Code)", 
            fg_color="#4b5563", # Neutral slate gray
            command=self._prompt_admin_unlock_all
        )
        self.unlock_btn.grid(row=row_after+4, column=0, columnspan=4, padx=10, pady=5, sticky="ew")
    
    def _prompt_admin_unlock_all(self):
        """Prompts for a code; if correct, unlocks every single input field on the form."""
        # checks if user has entered the unit id
        if not self.onb_entries["unit_id"].get():  # If no Unit ID is entered, prompt them to enter it first
            messagebox.showinfo("Error: Info Required","Please enter the Unit ID first in the form before unlocking.",) # Just show an OK dialog
            return
        # Open the CustomTkinter input dialog popup
        dialog = ctk.CTkInputDialog(
            text="Enter Admin Access Code to edit this tenant profile:", 
            title="Form Unlock"
        )

        self._load_tenant_to_ui()  # Load the tenant data first so they can see what they're unlocking before they enter the code
        
        entered_code = dialog.get_input()

        # Check your access code
        if entered_code == "1234":
            print("Access granted. Unlocking all fields for editing...")
            
            # 1. Loop through and unlock all entry fields dynamically
            for key, entry in self.onb_entries.items():
                entry.configure(state="normal")
            
            # 2. Unlock your combo menu dropdowns and extra inputs
            self.profession_combo.configure(state="normal")
            self.penalty_combo.configure(state="normal")
            self.brokerage_entry.configure(state="normal")
            
            # Optional UI feedback: change the status text color to show it's unlocked
            self.unlock_btn.configure(text="🔓 Editing Enabled", text_color="#d97706")
        else:
            if entered_code is not None:
                print("Incorrect code. Form remains locked.")
    
    def _check_and_update_pdf_button(self):
        """Checks if a PDF exists for the current Unit ID and transforms the button."""
        unit_id = self.onb_entries["unit_id"].get().strip()
        
        if not unit_id:
            self.pdf_status.configure(text="Enter Unit ID to check PDF status", text_color="gray")
            return

        # Query your database.py file
        documents = self.db.get_tenant_documents(unit_id)

        if documents and documents[0].get("file_path"):
            # Scenario A: PDF EXISTS -> Turn into a "View" button
            file_name = os.path.basename(documents[0]["file_path"])
            self.pdf_status.configure(text=f"Exists: {file_name}", text_color="#2b733e")
            
            self.pdf_action_btn.configure(
                text="View Agreement", 
                command=self._open_pdf  # Launches the viewer we fixed earlier
            )
        elif self.agreement_path.get():
            # Scenario B: Staged locally by user -> Show ready status
            file_name = os.path.basename(self.agreement_path.get())
            self.pdf_status.configure(text=f"Staged to Upload: {file_name}", text_color="#d97706") # Amber color
            self.pdf_action_btn.configure(text="Change Agreement (PDF)", fg_color="#4b5563", command=self._browse_pdf)
        else:
            # Scenario B: NO PDF -> Turn into an "Upload" button
            self.pdf_status.configure(text="No PDF attached to this unit", text_color="gray")
            
            self.pdf_action_btn.configure(
                text="Upload Agreement (PDF)", 
                fg_color="#a83232",  # Red/Alert color indicating it's missing
                command=self._browse_pdf  # Triggers the uploader
            )
    
    def _open_pdf(self):
        """Safely fetches and opens the stored PDF string for a specific unit."""
        unit_id = self.onb_entries["unit_id"].get()
        if not unit_id:
            print("Please enter a Unit ID first.")
            return

        # Safely pull the string value out of the first dictionary record
        pdf_path = self.db.get_tenant_documents(unit_id)[0]["file_path"]
        
        if not pdf_path:
            print("No documents found for this unit.")
            return

        if pdf_path and os.path.exists(pdf_path):
            if platform == "win32": # Windows
                os.startfile(pdf_path)
            elif platform == "darwin": # macOS
                subprocess.run(["open", pdf_path])
            else: # Linux
                subprocess.run(["xdg-open", pdf_path])
    
    def _browse_pdf(self):
        """Opens a file dialog allowing the user to select a PDF file."""
        file_path = filedialog.askopenfilename(
            title="Select Rental Agreement",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if file_path:
            self.agreement_path.set(file_path)
            # Update label to show just the file name cleanly
            file_name = os.path.basename(file_path)
            self.pdf_status.configure(text=f"Attached: {file_name}", text_color="#2b733e")
            self._check_and_update_pdf_button() # Update the button state in case it needs to change from Upload to View

    def _update_tenant_submit(self):
        """Gathers edited fields from the UI and applies changes to the database."""
        unit_id = self.onb_entries["unit_id"].get().strip()
        if not unit_id:
            print("Unit ID required to perform an update.")
            return

        # Build a kwargs dictionary out of your text entry widgets
        update_payload = {}
        for key, entry in self.onb_entries.items():
            if key != "unit_id":
                update_payload[key] = entry.get()

        # Add the dropdown fields into the payload package
        update_payload["profession_type"] = self.profession_combo.get()
        update_payload["notice_penalty_type"] = self.penalty_combo.get()

        # Execute your safe kwargs update method from database.py
        self.db.update_tenant(unit_id, **update_payload)
        if self.agreement_path.get():
            self.db.attach_document_to_tenant(unit_id, self.agreement_path.get())   # Safely attach the PDF path to the tenant's documents in the database
            self.agreement_path.set("")  # Clear the staged path after upload
        print(f"Successfully updated profiles details for Unit {unit_id}.")
        
        # Refresh any linked tables or global dropdown states across screens
        self._refresh_tenant_dropdowns()
        self.show_dashboard() # returns user to dashboard after update

    def _load_tenant_to_ui(self):
        """Pulls existing data from the database and fills the entry boxes."""
        unit_id = self.onb_entries["unit_id"].get()#.strip()
        self.agreement_path.set("")  # Clear any previously staged PDF path when loading new tenant data
        if not unit_id:
            print("Please enter a valid Unit ID to fetch data.")
            return

        # Call get_tenant from your database.py file
        tenant_data = self.db.get_tenant(unit_id)
        
        if not tenant_data:
            print(f"No active tenant found for Unit {unit_id}")
            return

        # 1. Autofill standard text entries dynamically
        for key, entry in self.onb_entries.items():
            if key != "unit_id":  # Don't overwrite the ID they just typed
                entry.delete(0, "end") # Clear whatever text was there before
                val = tenant_data.get(key)
                if val is not None:
                    entry.insert(0, str(val)) # insert View-only values
                    entry.configure(state="readonly") # Make sure it's  disabled 

        # 2. Autofill the dropdown combo boxes
        if tenant_data.get("profession_type"):
            self.profession_combo.set(tenant_data["profession_type"])
            
        if tenant_data.get("notice_penalty_type"):
            self.penalty_combo.set(tenant_data["notice_penalty_type"])
        
        self.profession_combo.configure(state="disabled")
        self.penalty_combo.configure(state="disabled")
        
        print(f"Data successfully loaded for Unit {unit_id}!")
    
    def _refresh_tenant_dropdowns(self):
        tenants = self.db.get_all_active_tenants()
        units = [t["unit_id"] for t in tenants]
        if units:
            self.util_unit_combo.configure(values=units)
            self.util_unit_combo.set(units[0])
            self._load_ledger_view(units[0])
        else:
            self.util_unit_combo.configure(values=["No Active Units"])
            self.util_unit_combo.set("No Active Units")

    # -----------------------------------------------------------------
    # ONBOARDING (Complete SRS fields)
    # -----------------------------------------------------------------
    def _build_onboarding(self):
        scroll = ctk.CTkScrollableFrame(self.onboard_frame, width=750, height=580)
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        #scroll.grid_columnconfigure((0,1), weight=1)  # Add this line back if you want the main content to stretch, but for now we want it fixed size with a scrollbar on the right

        # Scroll bar is fixed to the right no matter what # when you add the upper line delete this so that the content stays fixed.
        scroll.grid_columnconfigure(0, weight=0)  # Main content (stays fixed size)
        scroll.grid_columnconfigure(4, weight=1)  # Right spacer

        ctk.CTkLabel(scroll, text="Tenant Onboarding", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=15, sticky="w")

        self.onb_entries = {}
        fields = [
            ("unit_id", "Unit ID"),
            ("tenant_name", "Full Legal Name"),
            ("phone", "Phone"),
            ("email", "Email"),
            ("permanent_address", "Permanent Address"),
            ("govt_id_type", "Govt ID Type (Aadhaar/PAN)"),
            ("govt_id_number", "Govt ID Number"),
            ("base_rent", "Base Monthly Rent (₹)"),
            ("security_deposit_held", "Security Deposit (₹)"),
            ("parent_1_name", "Parent 1 Name"),
            ("parent_1_phone", "Parent 1 Phone"),
            ("parent_2_name", "Parent 2 Name"),
            ("parent_2_phone", "Parent 2 Phone"),
            ("organization_or_college", "Organization/College"),
            ("designation_or_course", "Designation/Course"),
            ("required_notice_days", "Required Notice Days"),
            ("onboarding_date", "Onboarding Date (YYYY-MM-DD)"),
            ("water_fixed_charge", "Water Fixed Charge (₹)")
        ]
        for i, (key, label) in enumerate(fields):
            row = (i // 2) + 1
            col = i % 2
            ctk.CTkLabel(scroll, text=label).grid(row=row, column=col*2, padx=5, pady=4, sticky="e")
            entry = ctk.CTkEntry(scroll, width=200)
            entry.grid(row=row, column=col*2+1, padx=5, pady=4, sticky="w")
            self.onb_entries[key] = entry
            if key == "onboarding_date":
                entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

        row_after = (len(fields)//2) + 2
        ctk.CTkLabel(scroll, text="Profession").grid(row=row_after, column=0, padx=5, pady=4, sticky="e")
        self.profession_combo = ctk.CTkOptionMenu(scroll, values=["Student", "Working Professional", "Government", "Private", "Other"])
        self.profession_combo.grid(row=row_after, column=1, padx=5, pady=4, sticky="w")

        ctk.CTkLabel(scroll, text="Penalty Type").grid(row=row_after, column=2, padx=5, pady=4, sticky="e")
        self.penalty_combo = ctk.CTkOptionMenu(scroll, values=["Forfeit Full Security", "Fixed Charge 5000", "Fixed Charge 10000"])
        self.penalty_combo.grid(row=row_after, column=3, padx=5, pady=4, sticky="w")

        ctk.CTkLabel(scroll, text="Brokerage Fee (₹)").grid(row=row_after+1, column=0, padx=5, pady=4, sticky="e")
        self.brokerage_entry = ctk.CTkEntry(scroll, width=200)
        self.brokerage_entry.grid(row=row_after+1, column=1, padx=5, pady=4, sticky="w")
        self.brokerage_entry.insert(0, "0")

        self.agreement_path = tk.StringVar()
        self.pdf_status = ctk.CTkLabel(scroll, text="No PDF attached", text_color="gray")
        self.pdf_status.grid(row=row_after+2, column=0, columnspan=2, padx=10, pady=5, sticky="w")
        ctk.CTkButton(scroll, text="Attach Rental Agreement (PDF)", command=self._select_pdf).grid(row=row_after+2, column=2, columnspan=2, padx=10, pady=5, sticky="ew")

        ctk.CTkButton(scroll, text="Onboard Tenant", fg_color="#2b733e", height=45, command=self._onboard_submit).grid(row=row_after+3, column=0, columnspan=4, padx=10, pady=20, sticky="ew")

    def _select_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if path:
            self.agreement_path.set(path)
            self.pdf_status.configure(text=f"Attached: {os.path.basename(path)}", text_color="#4CAF50")

    def _onboard_submit(self):
        data = {k: v.get().strip() for k, v in self.onb_entries.items()}
        data["profession_type"] = self.profession_combo.get()
        data["notice_penalty_type"] = self.penalty_combo.get()
        try:
            data["base_rent"] = float(data["base_rent"])
            data["security_deposit_held"] = float(data["security_deposit_held"])
            data["required_notice_days"] = int(data["required_notice_days"])
            brokerage = float(self.brokerage_entry.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Input Error", "Check numeric fields.")
            return
        if not data["unit_id"] or not data["tenant_name"] or not data["phone"]:
            messagebox.showerror("Input Error", "Unit ID, Name, Phone required.")
            return
        data["status"] = "Active"
        try:
            self.db.onboard_tenant(data, brokerage)
            if self.agreement_path.get():
                self.db.attach_rental_agreement(data["unit_id"], self.agreement_path.get())
            messagebox.showinfo("Success", f"Tenant {data['unit_id']} onboarded.")
            for e in self.onb_entries.values():
                e.delete(0, "end")
            self.onb_entries["onboarding_date"].insert(0, datetime.now().strftime("%Y-%m-%d"))
            self.brokerage_entry.delete(0, "end")
            self.brokerage_entry.insert(0, "0")
            self.pdf_status.configure(text="No PDF attached", text_color="gray")
            self.agreement_path.set("")
            self.show_dashboard()
        except Exception as err:
            messagebox.showerror("Error", str(err))

    # -----------------------------------------------------------------
    # UTILITIES & LEDGER
    # -----------------------------------------------------------------
    def _build_utilities(self):
        self.util_frame.grid_columnconfigure((0,1), weight=1)

        ctk.CTkLabel(self.util_frame, text="Target Unit", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.util_unit_combo = ctk.CTkOptionMenu(self.util_frame, values=[], command=self._load_ledger_view)
        self.util_unit_combo.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        self.elec_rate_label = ctk.CTkLabel(self.util_frame, text="Electricity: -- | --")
        self.elec_rate_label.grid(row=2, column=0, padx=10, pady=(0,5), sticky="w")
        self.water_rate_label = ctk.CTkLabel(self.util_frame, text="Water: -- | --")
        self.water_rate_label.grid(row=2, column=1, padx=10, pady=(0,5), sticky="w")
        ops = ctk.CTkFrame(self.util_frame, fg_color="#1e1e1e", corner_radius=8)
        ops.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        ops.grid_columnconfigure((0,1,2,3), weight=1)

        ctk.CTkLabel(ops, text="Current Reading").grid(row=0, column=0, padx=5, pady=5)
        self.reading_entry = ctk.CTkEntry(ops, placeholder_text="Meter reading")
        self.reading_entry.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        self.util_type_combo = ctk.CTkOptionMenu(ops, values=["Electricity", "Water"])
        self.util_type_combo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.meter_photo_path = tk.StringVar()
        self.photo_label = ctk.CTkLabel(ops, text="No photo", text_color="gray")
        self.photo_label.grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkButton(ops, text="Attach Photo", command=self._select_meter_photo).grid(row=1, column=2, padx=5, pady=5, sticky="ew")

        ctk.CTkButton(ops, text="Log Reading & Post", command=self._log_utility_reading).grid(row=1, column=3, padx=5, pady=5, sticky="ew")

        ctk.CTkLabel(ops, text="Period Start (YYYY-MM-DD)").grid(row=2, column=0, padx=5, pady=5)
        self.period_start = ctk.CTkEntry(ops)
        self.period_start.grid(row=3, column=0, padx=5, pady=5, sticky="ew")
        self.period_start.insert(0, datetime.now().replace(day=1).strftime("%Y-%m-%d"))

        ctk.CTkLabel(ops, text="Period End").grid(row=2, column=1, padx=5, pady=5)
        self.period_end = ctk.CTkEntry(ops)
        self.period_end.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        last_day = (datetime.now().replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        self.period_end.insert(0, last_day.strftime("%Y-%m-%d"))

        ctk.CTkButton(ops, text="Generate Statement", command=self._generate_invoice).grid(row=3, column=2, columnspan=2, padx=5, pady=5, sticky="ew")

        # --- Rate update button (new) ---
        self.btn_update_rates = ctk.CTkButton(self.util_frame, text="Modify Global Pricing Matrix", command=self._open_rate_dialog)
        self.btn_update_rates.grid(row=3, column=0, columnspan=1, padx=10, pady=5, sticky="ew")
        self.btn_post_fixed_water_charge = ctk.CTkButton(self.util_frame, text="Post Fixed Water Charge", command=lambda: (unit := self.util_unit_combo.get()) and [ self.db.post_fixed_water_charge(unit, datetime.now().replace(day=1).strftime("%Y-%m-%d")), self._display_ledger(unit) ])# self._load_ledger_view(self.util_unit_combo.get())])
        self.btn_post_fixed_water_charge.grid(row=3, column=1, columnspan=1, padx=10, pady=5, sticky="ew")

        manual_frame = ctk.CTkFrame(self.util_frame, fg_color="transparent")
        manual_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        manual_frame.grid_columnconfigure((0,1,2), weight=1)

        ctk.CTkButton(manual_frame, text="Post Payment", command=self._post_payment).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(manual_frame, text="Post Charge", command=self._post_charge).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(manual_frame, text="Run Late Fees", command=self._apply_late_fees).grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        # ledger goes below the manual frame
        self.ledger_box = ctk.CTkTextbox(self.util_frame, height=300, font=ctk.CTkFont(family="Courier", size=11))
        self.ledger_box.grid(row=5, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

    def _refresh_tenant_dropdowns(self):
        tenants = self.db.get_all_active_tenants()
        units = [t["unit_id"] for t in tenants]
        if units:
            self.util_unit_combo.configure(values=units)
            self.util_unit_combo.set(units[0])
            self._load_ledger_view(units[0])
        else:
            self.util_unit_combo.configure(values=["No Active Units"])
            self.util_unit_combo.set("No Active Units")

    def _load_ledger_view(self, unit_id):
        if unit_id == "No Active Units":
            return
        self.db.apply_late_fees(unit_id)
        self._display_ledger(unit_id)
        today = datetime.now().strftime("%Y-%m-%d")
        elec = self.db.get_active_rate("Electricity", today)
        water = self.db.get_active_rate("Water", today)
        if elec:
            self.elec_rate_label.configure(text=f"Elec: Base ₹{elec['landlord_base_rate']:.2f} | Charge ₹{elec['tenant_charge_rate']:.2f}")
        if water:
            self.water_rate_label.configure(text=f"Water: Base ₹{water['landlord_base_rate']:.2f} | Charge ₹{water['tenant_charge_rate']:.2f}")

    def _display_ledger(self, unit_id):
        ledger = self.db.get_ledger_for_tenant(unit_id)
        self.ledger_box.configure(state="normal")
        self.ledger_box.delete("1.0", tk.END)
        self.ledger_box.insert(tk.END, f"{'Date':<12} {'Type':<20} {'Description':<35} {'Amount':>10} {'Balance':>12}\n")
        self.ledger_box.insert(tk.END, "-" * 90 + "\n")
        for tx in ledger:
            self.ledger_box.insert(tk.END, f"{tx['transaction_date']:<12} {tx['transaction_type']:<20} {tx['description'][:33]:<35} ₹{tx['amount']:>9,.2f} ₹{tx['running_balance']:>11,.2f}\n")
        self.ledger_box.configure(state="disabled")

    def _select_meter_photo(self):
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if path:
            self.meter_photo_path.set(path)
            self.photo_label.configure(text=f"Photo: {os.path.basename(path)}", text_color="#4CAF50")

    def _log_utility_reading(self):
        unit = self.util_unit_combo.get()
        if unit == "No Active Units":
            return
        try:
            current = float(self.reading_entry.get().strip())
            u_type = self.util_type_combo.get()
            today = datetime.now().strftime("%Y-%m-%d")
            period = datetime.now().strftime("%B %Y")
            img_blob = None
            if self.meter_photo_path.get():
                with open(self.meter_photo_path.get(), "rb") as f:
                    img_blob = f.read()
            self.db.log_utility_reading(unit, u_type, period, current, today, img_blob)
            messagebox.showinfo("Success", "Reading logged and charge posted.")
            self.reading_entry.delete(0, "end")
            self.meter_photo_path.set("")
            self.photo_label.configure(text="No photo", text_color="gray")
            self._display_ledger(unit)
            self.show_dashboard()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _generate_invoice(self):
        unit = self.util_unit_combo.get()
        if unit == "No Active Units":
            return
        start = self.period_start.get().strip()
        end = self.period_end.get().strip()
        try:
            stmt = self.invoice_engine.generate_statement(unit, start, end)
            self.ledger_box.configure(state="normal")
            self.ledger_box.delete("1.0", tk.END)
            self.ledger_box.insert(tk.END, stmt)
            self.ledger_box.configure(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _post_payment(self):
        unit = self.util_unit_combo.get()
        if unit == "No Active Units": return
        self._amount_dialog("Payment Amount", lambda amt: self.db.post_payment(unit, amt, datetime.now().strftime("%Y-%m-%d")))

    def _post_charge(self):
        unit = self.util_unit_combo.get()
        if unit == "No Active Units": return
        self._amount_dialog("Charge Amount", lambda amt: self.db.post_charge(unit, "Maintenance Split", amt, datetime.now().strftime("%Y-%m-%d"), "Manual Charge"))

    def _apply_late_fees(self):
        unit = self.util_unit_combo.get()
        if unit == "No Active Units": return
        count = self.db.apply_late_fees(unit)
        messagebox.showinfo("Late Fees", f"{count} late fee(s) posted.")
        self._display_ledger(unit)
        self.show_dashboard()

    def _amount_dialog(self, title, callback):
        dialog = ctk.CTkInputDialog(text="Enter amount:", title=title)
        amt_str = dialog.get_input()
        if amt_str:
            try:
                amount = float(amt_str.strip())
                callback(amount)
                self._display_ledger(self.util_unit_combo.get())
                self.show_dashboard()
            except ValueError:
                messagebox.showerror("Error", "Invalid amount.")

    def _open_rate_dialog(self):
        """Opens a dialog to append a new utility rate tier (date‑effective)."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Update Global Utility Rate")
        dialog.geometry("350x300")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Utility Type:").pack(pady=(15, 2))
        rate_type = tk.StringVar(value="Electricity")
        ctk.CTkOptionMenu(dialog, variable=rate_type, values=["Electricity", "Water"]).pack(pady=2)

        ctk.CTkLabel(dialog, text="Landlord Base Rate (₹/unit):").pack(pady=(10, 2))
        landlord_entry = ctk.CTkEntry(dialog)
        landlord_entry.pack(pady=2)

        ctk.CTkLabel(dialog, text="Tenant Charge Rate (₹/unit):").pack(pady=(10, 2))
        tenant_entry = ctk.CTkEntry(dialog)
        tenant_entry.pack(pady=2)

        def save_rate():
            try:
                lr = float(landlord_entry.get().strip())
                tr = float(tenant_entry.get().strip())
                self.db.add_utility_rate(
                    datetime.now().strftime("%Y-%m-%d"),
                    rate_type.get(),
                    lr,
                    tr
                )
                messagebox.showinfo("Success", "Rate updated. It will apply from today onward.", parent=dialog)
                dialog.destroy()
                # Refresh the rate display (if any) – you can add a label refresh here
                self._load_ledger_view(self.util_unit_combo.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid numbers.", parent=dialog)

        ctk.CTkButton(dialog, text="Save New Rate Tier", command=save_rate, fg_color="#2b733e").pack(pady=20)

    # -----------------------------------------------------------------
    # ARCHIVE (Move-Out + Read-Only)
    # -----------------------------------------------------------------
    def _build_archive(self):
        self.archive_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.archive_frame, text="Move-Out & Archive", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.moveout_combo = ctk.CTkOptionMenu(self.archive_frame, values=[], command=self._preview_moveout)
        self.moveout_combo.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.moveout_balance = ctk.CTkLabel(self.archive_frame, text="Outstanding: --")
        self.moveout_balance.grid(row=2, column=0, padx=10, pady=2, sticky="w")
        self.moveout_penalty = ctk.CTkLabel(self.archive_frame, text="Penalty: --")
        self.moveout_penalty.grid(row=3, column=0, padx=10, pady=2, sticky="w")
        self.moveout_refund = ctk.CTkLabel(self.archive_frame, text="Net Refund: --")
        self.moveout_refund.grid(row=4, column=0, padx=10, pady=2, sticky="w")

        ctk.CTkButton(self.archive_frame, text="Execute Move-Out (Archive & Purge)", fg_color="#8b0000", command=self._execute_moveout).grid(row=5, column=0, padx=10, pady=15, sticky="ew")

        ctk.CTkLabel(self.archive_frame, text="--- Import Archive ---", font=ctk.CTkFont(weight="bold")).grid(row=6, column=0, padx=10, pady=(20,5), sticky="w")
        ctk.CTkButton(self.archive_frame, text="Open Archive Database", command=self._open_archive).grid(row=7, column=0, padx=10, pady=5, sticky="ew")
        self.archive_output = ctk.CTkTextbox(self.archive_frame, height=280, font=ctk.CTkFont(family="Courier", size=11))
        self.archive_output.grid(row=8, column=0, padx=10, pady=10, sticky="nsew")

    def _refresh_moveout_dropdown(self):
        tenants = self.db.get_all_active_tenants()
        units = [t["unit_id"] for t in tenants]
        self.moveout_combo.configure(values=units if units else ["No Active Units"])
        if units:
            self.moveout_combo.set(units[0])
            self._preview_moveout(units[0])

    def _preview_moveout(self, unit_id):
        if unit_id == "No Active Units":
            return
        tenant = self.db.get_tenant(unit_id)
        if not tenant:
            return
        bal = self.db.get_current_balance(unit_id)
        deposit = tenant["security_deposit_held"]
        penalty = 0.0
        if tenant["notice_penalty_type"] == "Forfeit Full Security":
            penalty = deposit
        elif "Fixed" in tenant["notice_penalty_type"]:
            try:
                penalty = float(tenant["notice_penalty_type"].split()[-1])
            except:
                penalty = 0.0
        refund = deposit - bal - penalty
        self.moveout_balance.configure(text=f"Outstanding Balance: ₹{bal:,.2f}")
        self.moveout_penalty.configure(text=f"Penalty: ₹{penalty:,.2f}")
        self.moveout_refund.configure(text=f"Net Refund: ₹{refund:,.2f}")

    def _execute_moveout(self):
        unit = self.moveout_combo.get()
        if unit == "No Active Units":
            return
        if not messagebox.askyesno("Confirm", f"Archive and permanently remove {unit}?"):
            return
        try:
            refund = self.db.archive_tenant(unit, datetime.now().strftime("%Y-%m-%d"))
            messagebox.showinfo("Success", f"Tenant archived. Net refund: ₹{refund:,.2f}")
            self._refresh_moveout_dropdown()
            self.show_dashboard()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _open_archive(self):
        path = filedialog.askopenfilename(filetypes=[("Database files", "*.db")])
        if not path:
            return
        try:
            conn = DatabaseManager.open_archive_read_only(path)
            cursor = conn.cursor()
            self.archive_output.configure(state="normal")
            self.archive_output.delete("1.0", tk.END)
            tenant = cursor.execute("SELECT * FROM Tenants LIMIT 1").fetchone()
            if tenant:
                self.archive_output.insert(tk.END, f"Archived Unit: {tenant['unit_id']} - {tenant['tenant_name']}\nPhone: {tenant['phone']}\n\n")
            ledger = cursor.execute("SELECT * FROM Financial_Ledger ORDER BY transaction_date").fetchall()
            self.archive_output.insert(tk.END, f"{'Date':<12} {'Type':<20} {'Description':<35} {'Amount':>10}\n")
            self.archive_output.insert(tk.END, "-"*80 + "\n")
            for row in ledger:
                self.archive_output.insert(tk.END, f"{row['transaction_date']:<12} {row['transaction_type']:<20} {row['description'][:33]:<35} ₹{row['amount']:>9,.2f}\n")
            self.archive_output.configure(state="disabled")
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open archive: {e}")


if __name__ == "__main__":
    app = PropManagerApp()
    app.mainloop()