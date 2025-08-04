#!/usr/bin/env python3
"""
Simple GUI for running Freqtrade backtests
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import json
from datetime import datetime, timedelta
import glob

class BacktestGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Freqtrade Backtest GUI")
        self.root.geometry("600x500")
        
        # Variables
        self.strategy_var = tk.StringVar()
        self.timeframe_var = tk.StringVar(value="15m")
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()
        self.output_folder_var = tk.StringVar()
        self.config_file_var = tk.StringVar(value="config_dip_testing.json")
        self.last_backtest_output = ""  # Store the last backtest output
        
        # Set default dates (last month, but ensure we don't go into the future)
        end_date = datetime.now() - timedelta(days=1)  # Yesterday to avoid future dates
        start_date = end_date - timedelta(days=30)
        self.start_date_var.set(start_date.strftime("%Y%m%d"))
        self.end_date_var.set(end_date.strftime("%Y%m%d"))
        
        self.setup_ui()
        self.load_strategies()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Freqtrade Backtest Runner", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Strategy selection
        ttk.Label(main_frame, text="Strategy:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.strategy_combo = ttk.Combobox(main_frame, textvariable=self.strategy_var, state="readonly", width=40)
        self.strategy_combo.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Config file selection
        ttk.Label(main_frame, text="Config File:").grid(row=2, column=0, sticky=tk.W, pady=5)
        config_frame = ttk.Frame(main_frame)
        config_frame.grid(row=2, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        config_frame.columnconfigure(0, weight=1)
        
        self.config_entry = ttk.Entry(config_frame, textvariable=self.config_file_var)
        self.config_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        config_button = ttk.Button(config_frame, text="Browse", command=self.browse_config)
        config_button.grid(row=0, column=1)
        
        # Timeframe selection
        ttk.Label(main_frame, text="Timeframe:").grid(row=3, column=0, sticky=tk.W, pady=5)
        timeframe_combo = ttk.Combobox(main_frame, textvariable=self.timeframe_var, 
                                     values=["1m", "5m", "15m", "30m", "1h", "4h", "1d"], 
                                     state="readonly", width=40)
        timeframe_combo.grid(row=3, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Date selection
        ttk.Label(main_frame, text="Start Date (YYYYMMDD):").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=40).grid(row=4, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(main_frame, text="End Date (YYYYMMDD):").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=40).grid(row=5, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Output folder selection
        ttk.Label(main_frame, text="Output Folder:").grid(row=6, column=0, sticky=tk.W, pady=5)
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=6, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        output_frame.columnconfigure(0, weight=1)
        
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_folder_var)
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        output_button = ttk.Button(output_frame, text="Browse", command=self.browse_output_folder)
        output_button.grid(row=0, column=1)
        
        # Quick date buttons
        date_frame = ttk.LabelFrame(main_frame, text="Quick Date Selection", padding="5")
        date_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Button(date_frame, text="Last 7 Days", command=self.set_last_7_days).grid(row=0, column=0, padx=5)
        ttk.Button(date_frame, text="Last 30 Days", command=self.set_last_30_days).grid(row=0, column=1, padx=5)
        ttk.Button(date_frame, text="Last 90 Days", command=self.set_last_90_days).grid(row=0, column=2, padx=5)
        ttk.Button(date_frame, text="Last Year", command=self.set_last_year).grid(row=0, column=3, padx=5)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=3, pady=20)
        
        # Run button
        run_button = ttk.Button(button_frame, text="Run Backtest", command=self.run_backtest)
        run_button.pack(side=tk.LEFT, padx=5)
        
        # Download data button
        download_button = ttk.Button(button_frame, text="Download Data", command=self.download_data)
        download_button.pack(side=tk.LEFT, padx=5)
        
        # Reset dates button
        reset_button = ttk.Button(button_frame, text="Reset Dates", command=self.reset_dates)
        reset_button.pack(side=tk.LEFT, padx=5)
        
        # Test March 2024 button (we know this data exists)
        test_button = ttk.Button(button_frame, text="Test March 2024", command=self.set_march_2024)
        test_button.pack(side=tk.LEFT, padx=5)
        
        # Delete data button
        delete_button = ttk.Button(button_frame, text="Delete Data", command=self.delete_data)
        delete_button.pack(side=tk.LEFT, padx=5)
        
        # View report button
        report_button = ttk.Button(button_frame, text="View Report", command=self.view_report)
        report_button.pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready to run backtest")
        self.status_label.grid(row=10, column=0, columnspan=3, pady=5)
        
    def load_strategies(self):
        """Load available strategies from the strategies folder"""
        strategies = []
        strategy_path = "user_data/strategies"
        
        if os.path.exists(strategy_path):
            for file in glob.glob(os.path.join(strategy_path, "*.py")):
                if not file.endswith("__init__.py"):
                    strategy_name = os.path.basename(file).replace(".py", "")
                    strategies.append(strategy_name)
        
        self.strategy_combo['values'] = sorted(strategies)
        if strategies:
            self.strategy_combo.set(strategies[0])
    
    def browse_config(self):
        """Browse for config file"""
        filename = filedialog.askopenfilename(
            title="Select Config File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.config_file_var.set(filename)
    
    def browse_output_folder(self):
        """Browse for output folder"""
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_folder_var.set(folder)
    
    def set_last_7_days(self):
        end_date = datetime.now() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=7)
        self.start_date_var.set(start_date.strftime("%Y%m%d"))
        self.end_date_var.set(end_date.strftime("%Y%m%d"))
    
    def set_last_30_days(self):
        end_date = datetime.now() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=30)
        self.start_date_var.set(start_date.strftime("%Y%m%d"))
        self.end_date_var.set(end_date.strftime("%Y%m%d"))
    
    def set_last_90_days(self):
        end_date = datetime.now() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=90)
        self.start_date_var.set(start_date.strftime("%Y%m%d"))
        self.end_date_var.set(end_date.strftime("%Y%m%d"))
    
    def set_last_year(self):
        end_date = datetime.now() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=365)
        self.start_date_var.set(start_date.strftime("%Y%m%d"))
        self.end_date_var.set(end_date.strftime("%Y%m%d"))
    
    def validate_inputs(self):
        """Validate user inputs"""
        if not self.strategy_var.get():
            self.show_error_in_status("Please select a strategy")
            return False
        
        if not self.config_file_var.get():
            self.show_error_in_status("Please select a config file")
            return False
        
        if not os.path.exists(self.config_file_var.get()):
            self.show_error_in_status("Config file does not exist")
            return False
        
        if not self.start_date_var.get() or not self.end_date_var.get():
            self.show_error_in_status("Please enter start and end dates")
            return False
        
        try:
            start_date = datetime.strptime(self.start_date_var.get(), "%Y%m%d")
            end_date = datetime.strptime(self.end_date_var.get(), "%Y%m%d")
        except ValueError:
            self.show_error_in_status("Invalid date format. Use YYYYMMDD")
            return False
        
        # Check if dates are in the future
        if start_date > datetime.now() or end_date > datetime.now():
            self.show_error_in_status("Cannot test future dates. Use historical dates only.")
            return False
        
        # Check if start date is before end date
        if start_date >= end_date:
            self.show_error_in_status("Start date must be before end date")
            return False
        
        if not self.output_folder_var.get():
            self.show_error_in_status("Please select an output folder")
            return False
        
        return True
    
    def run_backtest(self):
        """Run the backtest command"""
        if not self.validate_inputs():
            return
        
        # Prepare command
        timerange = f"{self.start_date_var.get()}-{self.end_date_var.get()}"
        
        cmd = [
            "freqtrade", "backtesting",
            "--config", self.config_file_var.get(),
            "--strategy", self.strategy_var.get(),
            "--timerange", timerange,
            "--timeframe", self.timeframe_var.get()
        ]
        
        # Add output folder if specified
        if self.output_folder_var.get():
            output_folder = self.output_folder_var.get()
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)
            
            # Create timestamp for unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            strategy_name = self.strategy_var.get()
            output_file = os.path.join(output_folder, f"backtest_{strategy_name}_{timestamp}.json")
            
            cmd.extend(["--export", "trades", "--export-filename", output_file])
        
        # Update UI
        self.status_label.config(text="Running backtest...")
        self.progress.start()
        self.root.update()
        
        try:
            # Run the command
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd(), timeout=300)  # 5 minute timeout
            
            if result.returncode == 0:
                self.status_label.config(text="Backtest completed successfully!")
                # Store the output for viewing
                self.last_backtest_output = result.stdout
                # Use non-blocking message
                self.show_non_blocking_message("Success", "Backtest completed successfully! Click 'View Report' to see results.")
                
                # Show output folder if specified
                if self.output_folder_var.get():
                    self.show_non_blocking_message("Output", f"Results saved to: {self.output_folder_var.get()}")
            else:
                error_msg = result.stderr if result.stderr else result.stdout if result.stdout else "Unknown error occurred"
                self.status_label.config(text="Backtest failed")
                # Store error output for viewing
                self.last_backtest_output = f"ERROR:\n{error_msg}"
                # Show error in status instead of blocking dialog
                self.show_error_in_status(f"Backtest failed: {error_msg[:200]}...")
                
        except subprocess.TimeoutExpired:
            self.status_label.config(text="Backtest timed out (5 minutes)")
            self.show_error_in_status("Backtest timed out after 5 minutes")
        except Exception as e:
            self.status_label.config(text="Backtest failed")
            self.show_error_in_status(f"Failed to run backtest: {str(e)}")
        
        finally:
            self.progress.stop()
    
    def show_non_blocking_message(self, title, message):
        """Show a non-blocking message using a toplevel window"""
        try:
            # Create a simple toplevel window
            msg_window = tk.Toplevel(self.root)
            msg_window.title(title)
            msg_window.geometry("400x150")
            msg_window.resizable(False, False)
            
            # Center the window
            msg_window.transient(self.root)
            msg_window.grab_set()
            
            # Add message
            ttk.Label(msg_window, text=message, wraplength=350, justify="center").pack(expand=True, fill="both", padx=20, pady=20)
            
            # Add close button
            ttk.Button(msg_window, text="OK", command=msg_window.destroy).pack(pady=10)
            
            # Auto-close after 3 seconds
            msg_window.after(3000, msg_window.destroy)
            
        except Exception:
            # Fallback to regular messagebox if toplevel fails
            messagebox.showinfo(title, message)
    
    def show_error_in_status(self, error_message):
        """Show error message in status bar instead of blocking dialog"""
        self.status_label.config(text=error_message)
        # Also log to console for debugging
        print(f"Error: {error_message}")
    
    def download_data(self):
        """Download data for the selected date range"""
        if not self.validate_inputs():
            return
        
        # Get pairs from config file
        try:
            with open(self.config_file_var.get(), 'r') as f:
                config = json.load(f)
                pairs = config.get('exchange', {}).get('pair_whitelist', [])
        except Exception as e:
            self.show_error_in_status(f"Error reading config file: {str(e)}")
            return
        
        if not pairs:
            self.show_error_in_status("No pairs found in config file")
            return
        
        # Prepare download command
        timerange = f"{self.start_date_var.get()}-{self.end_date_var.get()}"
        
        cmd = [
            "freqtrade", "download-data",
            "--config", self.config_file_var.get(),
            "--pairs", *pairs,
            "--timeframe", self.timeframe_var.get(),
            "--timerange", timerange
        ]
        
        # Update UI
        self.status_label.config(text="Downloading data...")
        self.progress.start()
        self.root.update()
        
        try:
            # Run the command
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd(), timeout=600)  # 10 minute timeout
            
            if result.returncode == 0:
                self.status_label.config(text="Data download completed!")
                self.show_non_blocking_message("Success", "Data download completed successfully!")
            else:
                error_msg = result.stderr if result.stderr else result.stdout if result.stdout else "Unknown error occurred"
                self.status_label.config(text="Data download failed")
                self.show_error_in_status(f"Data download failed: {error_msg[:200]}...")
                
        except subprocess.TimeoutExpired:
            self.status_label.config(text="Data download timed out (10 minutes)")
            self.show_error_in_status("Data download timed out after 10 minutes")
        except Exception as e:
            self.status_label.config(text="Data download failed")
            self.show_error_in_status(f"Failed to download data: {str(e)}")
        
        finally:
            self.progress.stop()
    
    def reset_dates(self):
        """Reset dates to default (last 30 days)"""
        end_date = datetime.now() - timedelta(days=1)  # Yesterday to avoid future dates
        start_date = end_date - timedelta(days=30)
        self.start_date_var.set(start_date.strftime("%Y%m%d"))
        self.end_date_var.set(end_date.strftime("%Y%m%d"))
        self.status_label.config(text="Dates reset to last 30 days")
    
    def set_march_2024(self):
        """Set dates to March 2024 (we know this data exists)"""
        self.start_date_var.set("20240301")
        self.end_date_var.set("20240331")
        self.status_label.config(text="Dates set to March 2024 (known good data)")
    
    def delete_data(self):
        """Delete all downloaded data"""
        # Get exchange name from config
        try:
            with open(self.config_file_var.get(), 'r') as f:
                config = json.load(f)
                exchange_name = config.get('exchange', {}).get('name', 'binanceus')
        except Exception as e:
            self.show_error_in_status(f"Error reading config file: {str(e)}")
            return
        
        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Deletion", 
            f"This will delete ALL downloaded data for {exchange_name}.\n\n"
            "This action cannot be undone.\n\n"
            "Are you sure you want to continue?"
        )
        
        if not confirm:
            return
        
        # Path to data directory
        data_dir = os.path.join("user_data", "data", exchange_name)
        
        if not os.path.exists(data_dir):
            self.show_error_in_status(f"No data directory found: {data_dir}")
            return
        
        try:
            # Count files before deletion
            file_count = 0
            total_size = 0
            
            for root, dirs, files in os.walk(data_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    file_count += 1
                    total_size += os.path.getsize(file_path)
            
            # Delete all files and directories
            import shutil
            shutil.rmtree(data_dir)
            
            # Show success message
            size_mb = total_size / (1024 * 1024)
            self.status_label.config(text=f"Deleted {file_count} files ({size_mb:.1f} MB)")
            self.show_non_blocking_message(
                "Data Deleted", 
                f"Successfully deleted {file_count} files\n({size_mb:.1f} MB freed)"
            )
            
        except Exception as e:
            self.show_error_in_status(f"Error deleting data: {str(e)}")
    
    def view_report(self):
        """Display the last backtest report in a window"""
        if not self.last_backtest_output:
            self.show_error_in_status("No backtest results available. Run a backtest first.")
            return
        
        # Create a new window for the report
        report_window = tk.Toplevel(self.root)
        report_window.title("Backtest Report")
        report_window.geometry("800x600")
        report_window.resizable(True, True)
        
        # Center the window
        report_window.transient(self.root)
        
        # Create main frame
        main_frame = ttk.Frame(report_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Backtest Report", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Text widget
        text_widget = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, font=("Courier", 10))
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbar
        scrollbar.config(command=text_widget.yview)
        
        # Insert the report content
        text_widget.insert(tk.END, self.last_backtest_output)
        
        # Make text read-only
        text_widget.config(state=tk.DISABLED)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        # Copy to clipboard button
        copy_button = ttk.Button(button_frame, text="Copy to Clipboard", command=lambda: self.copy_to_clipboard(self.last_backtest_output))
        copy_button.pack(side=tk.LEFT, padx=5)
        
        # Save to file button
        save_button = ttk.Button(button_frame, text="Save to File", command=lambda: self.save_report_to_file(self.last_backtest_output))
        save_button.pack(side=tk.LEFT, padx=5)
        
        # Close button
        close_button = ttk.Button(button_frame, text="Close", command=report_window.destroy)
        close_button.pack(side=tk.LEFT, padx=5)
        
        # Focus on the window
        report_window.focus_set()
    
    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.show_non_blocking_message("Copied", "Report copied to clipboard!")
        except Exception as e:
            self.show_error_in_status(f"Failed to copy to clipboard: {str(e)}")
    
    def save_report_to_file(self, text):
        """Save report to a file"""
        try:
            filename = filedialog.asksaveasfilename(
                title="Save Report",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            
            if filename:
                with open(filename, 'w') as f:
                    f.write(text)
                self.show_non_blocking_message("Saved", f"Report saved to: {filename}")
        except Exception as e:
            self.show_error_in_status(f"Failed to save report: {str(e)}")

def main():
    root = tk.Tk()
    app = BacktestGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 