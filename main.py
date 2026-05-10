# --- M-D Remittances Intelligence Engine ---
# This file orchestrates the scraping process from multiple sources (World Bank, IMF, UN, etc.)
# and merges them into a single final file for research and analysis.

import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# Setup project root in Python path to ensure modules are imported correctly
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# Force UTF-8 encoding for Windows compatibility to support special characters in terminal
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from pyfiglet import Figlet

# Import data scrapers and the merge engine
from scrapers.worldbank import WorldBankScraper
from scrapers.imf import IMFScraper
from scrapers.rpw import RPWScraper
from scrapers.fred import FREDScraper
from scrapers.un_sdg import UNSDGScraper
from merge import merge_master

console = Console()

def get_styled_logo():
    """Generates a professional ASCII logo for the project."""
    f = Figlet(font='block')
    logo_text = f.renderText('M-D')
    return Text(logo_text, style="bold #d97757")

def display_banner():
    """Displays the main CLI welcome banner."""
    console.clear()
    
    header_text = Text(" * Welcome to M-D Intelligence research preview!", style="white")
    console.print(Panel(header_text, border_style="#d97757", padding=(0, 1), expand=False))
    
    console.print(get_styled_logo())
    console.print(f"[dim]Intelligence session started: {datetime.now():%Y-%m-%d %H:%M:%S}[/dim]\n")

def display_info_panel():
    """Displays security notes and information about data sources."""
    console.print("[bold white]Security notes:[/bold white]\n")
    
    notes = [
        ("1. M-D is currently in research preview", "This version may have limitations or unexpected behaviors."),
        ("2. Data Intelligence verification", "Always review synthesized datasets, especially when using for research."),
        ("3. Trusted data sources only", "Direct integration with World Bank, IMF, and FRED official APIs.")
    ]
    
    for i, (title, desc) in enumerate(notes, 1):
        console.print(f"{i}. [bold white]{title}[/bold white]")
        console.print(f"   [dim]{desc}[/dim]\n")

    console.print("[bold #5085e8]Press Enter to continue...[/bold #5085e8]", end="")
    input()

def get_user_filters():
    """Interactive interface to prompt for filters (years, countries, regions)."""
    filters = {
        "start_year": 2010,
        "end_year": 2023,
        "countries": [],
        "region": None
    }
    
    while True:
        display_banner()
        console.print("[bold orange1]⚙ CONFIGURATION INTERFACE[/bold orange1]\n")
        
        # Display current configuration in a small table
        status = Table.grid(padding=(0, 2))
        status.add_column(style="dim")
        status.add_column(style="white")
        
        status.add_row("Temporal Scope:", f"{filters['start_year']} - {filters['end_year']}")
        status.add_row("Geographic Focus:", "ALL" if not filters['countries'] and not filters['region'] else 
                      (f"Countries: {', '.join(filters['countries'])}" if filters['countries'] else f"Region: {filters['region']}"))
        
        console.print(Panel(status, title="[dim]Current Config[/dim]", border_style="dim", expand=False))
        console.print("")

        # Menu options
        console.print("1. [bold white]Set Year Range[/bold white] [dim](Default: 2010-2023)[/dim]")
        console.print("2. [bold white]Filter by Countries[/bold white] [dim](ISO-3 codes)[/dim]")
        console.print("3. [bold white]Filter by Region[/bold white] [dim](Africa, Asia, etc.)[/dim]")
        console.print("4. [bold green]START INTELLIGENCE SEQUENCE[/bold green]")
        console.print("0. [bold red]Exit[/bold red]")
        
        choice = Prompt.ask("\n[bold cyan]Select an option[/bold cyan]", choices=["1", "2", "3", "4", "0"])

        if choice == "1":
            filters["start_year"] = IntPrompt.ask("   Enter start year", default=2010)
            filters["end_year"] = IntPrompt.ask("   Enter end year", default=2023)
        elif choice == "2":
            codes = Prompt.ask("   Enter ISO-3 codes separated by space (e.g. EGY MEX PHL) or 'back'").upper()
            if codes != "BACK":
                filters["countries"] = codes.split()
                filters["region"] = None 
        elif choice == "3":
            reg = Prompt.ask("   Enter region name (e.g. Africa, Europe) or 'back'")
            if reg.upper() != "BACK":
                filters["region"] = reg
                filters["countries"] = [] 
        elif choice == "4":
            break
        elif choice == "0":
            sys.exit(0)
            
    return filters

def display_section(title: str):
    """Prints standardized section headers for each stage of data retrieval."""
    console.print(f"\n[bold #d97757]● {title}[/bold #d97757]")
    console.print("[dim]" + "━" * 55 + "[/dim]")

def main():
    """Main application entry point."""
    parser = argparse.ArgumentParser(description="M-D Remittances Intelligence Engine")
    parser.add_argument("--skip-wb", action="store_true")
    parser.add_argument("--skip-imf", action="store_true")
    parser.add_argument("--skip-rpw", action="store_true")
    parser.add_argument("--skip-fred", action="store_true")
    parser.add_argument("--merge-only", action="store_true")
    args = parser.parse_args()

    display_banner()
    display_info_panel()
    
    # Capture user requirements
    filters = get_user_filters()
    start_yr = filters["start_year"]
    end_yr = filters["end_year"]
    
    console.clear()
    display_banner()
    console.print(f"\n[bold cyan]Initiating intelligence synchronization for period {start_yr}-{end_yr}...[/bold cyan]")
    time.sleep(1)
    
    start_time = time.time()
    execution_results = {}

    # 1. World Bank Data Sequence
    if not args.merge_only and not args.skip_wb:
        display_section("Synchronizing World Bank Intelligence Registry")
        try:
            with console.status("[bold green]Collecting World Bank Observations...", spinner="dots"):
                scraper = WorldBankScraper(delay=0.3)
                data = scraper.scrape(start=start_yr, end=end_yr)
                execution_results["World Bank"] = len(data)
            console.print(f"  [bold green]SUCCESS[/bold green] | Observations synchronized: [cyan]{len(data):,}[/cyan]")
        except Exception as e:
            console.print(f"  [bold red]FAILURE[/bold red] | Synchronization error: {e}")

    # 2. IMF Data Sequence
    if not args.merge_only and not args.skip_imf:
        display_section("Synchronizing IMF DataMapper Registry")
        try:
            with console.status("[bold green]Collecting IMF Macroeconomic Data...", spinner="dots"):
                scraper = IMFScraper(delay=2.0)
                data = scraper.scrape(start=start_yr, end=end_yr)
                execution_results["IMF"] = len(data)
            console.print(f"  [bold green]SUCCESS[/bold green] | Observations synchronized: [cyan]{len(data):,}[/cyan]")
        except Exception as e:
            console.print(f"  [bold red]FAILURE[/bold red] | Synchronization error: {e}")

    # 3. Remittance Price (RPW) Data Sequence
    if not args.merge_only and not args.skip_rpw:
        display_section("Synchronizing Remittance Price (RPW) Registry")
        try:
            with console.status("[bold green]Collecting Global Corridor Intelligence...", spinner="dots"):
                scraper = RPWScraper(delay=2.0)
                data = scraper.scrape(start=start_yr, end=end_yr)
                execution_results["RPW"] = len(data)
            console.print(f"  [bold green]SUCCESS[/bold green] | Observations synchronized: [cyan]{len(data):,}[/cyan]")
        except Exception as e:
            console.print(f"  [bold red]FAILURE[/bold red] | Synchronization error: {e}")

    # 4. FRED Financial Data Sequence
    if not args.merge_only and not args.skip_fred:
        display_section("Synchronizing FRED Financial Intelligence")
        try:
            with console.status("[bold green]Collecting FRED Financial Series...", spinner="dots"):
                scraper = FREDScraper(delay=1.0, retries=10)
                fx_data, macro_data = scraper.scrape(
                    start_date=f"{start_yr}-01-01",
                    end_date=f"{end_yr}-12-31"
                )
                execution_results["FRED FX"] = len(fx_data)
                execution_results["FRED Macro"] = len(macro_data)
            console.print(f"  [bold green]SUCCESS[/bold green] | FX: [cyan]{len(fx_data):,}[/cyan] | Macro: [cyan]{len(macro_data):,}[/cyan]")
        except Exception as e:
            console.print(f"  [bold red]FAILURE[/bold red] | Synchronization error: {e}")

    # 5. UN SDG Data Sequence
    if not args.merge_only:
        display_section("Synchronizing UN Sustainable Development Goals (SDG)")
        try:
            with console.status("[bold green]Collecting UN SDG Indicators...", spinner="dots"):
                scraper = UNSDGScraper(delay=1.0)
                data = scraper.scrape(start=start_yr, end=end_yr)
                execution_results["UN SDG"] = len(data)
            console.print(f"  [bold green]SUCCESS[/bold green] | Observations synchronized: [cyan]{len(data):,}[/cyan]")
        except Exception as e:
            console.print(f"  [bold red]FAILURE[/bold red] | Synchronization error: {e}")

    # 6. Final Synthesis Phase
    display_section("Executing Master Dataset Synthesis")
    try:
        with console.status("[bold yellow]Synthesizing Master Intelligence Dataset...", spinner="aesthetic"):
            master_data = merge_master(filters=filters)
            execution_results["Master Dataset"] = len(master_data)
        console.print(f"  [bold green]SUCCESS[/bold green] | Master Dataset synthesized with [cyan]{len(master_data):,}[/cyan] entities")
    except Exception as e:
        console.print(f"  [bold red]FAILURE[/bold red] | Synthesis critical error: {e}")

    # Generate final summary table
    total_elapsed = time.time() - start_time
    
    summary_table = Table(title="[bold #d97757]INTELLIGENCE SUMMARY[/bold #d97757]", border_style="#d97757")
    summary_table.add_column("Source Stream", style="cyan")
    summary_table.add_column("Records", justify="right", style="green")
    
    for source, count in execution_results.items():
        summary_table.add_row(source, f"{count:,}")
    
    console.print("\n")
    console.print(summary_table)
    
    # Final success message
    final_status = Text.assemble(
        ("\nOperation Finalized | Total Elapsed Time: ", "bold green"),
        (f"{total_elapsed/60:.1f} minutes", "bold white"),
        ("\nOutput Repository: ", "bold white"),
        ("data/merged/master_remittances_dataset.csv", "cyan")
    )
    console.print(Panel(final_status, border_style="#d97757", expand=False))

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]Intelligence sequence terminated by operator.[/bold red]")
        sys.exit(0)
