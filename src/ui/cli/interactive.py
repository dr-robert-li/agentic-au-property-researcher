"""
Interactive CLI for Australian Property Research using prompt_toolkit and rich.

Provides a user-friendly terminal interface with autocomplete and validation.
"""
import sys
from pathlib import Path
from typing import List

from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.validation import Validator, ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import settings, regions_data
from models.inputs import UserInput
from app import run_research_pipeline


console = Console()


class PriceValidator(Validator):
    """Validate price input."""

    def validate(self, document):
        text = document.text
        if not text:
            raise ValidationError(message="Price is required")
        try:
            price = float(text)
            if price <= 0:
                raise ValidationError(message="Price must be positive")
            if price < 100000:
                raise ValidationError(message="Price seems too low (minimum $100,000)")
            if price > 10000000:
                raise ValidationError(message="Price seems too high (maximum $10,000,000)")
        except ValueError:
            raise ValidationError(message="Please enter a valid number")


class NumSuburbsValidator(Validator):
    """Validate number of suburbs."""

    def validate(self, document):
        text = document.text
        if not text:
            raise ValidationError(message="Number of suburbs is required")
        try:
            num = int(text)
            if num <= 0:
                raise ValidationError(message="Must be at least 1")
            if num > 50:
                raise ValidationError(message="Maximum 50 suburbs recommended")
        except ValueError:
            raise ValidationError(message="Please enter a valid integer")


def print_welcome():
    """Print welcome banner."""
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]🏘️  Australian Property Research[/bold cyan]\n"
            "[dim]AI-Powered Investment Analysis for Australian Real Estate[/dim]",
            border_style="cyan"
        )
    )
    console.print()


def select_provider() -> str:
    """Interactive provider selection. Returns provider name."""
    available = settings.AVAILABLE_PROVIDERS

    if len(available) == 1:
        provider = available[0]
        label = "Perplexity" if provider == "perplexity" else "Anthropic Claude"
        console.print(f"[dim]Provider: {label} (only provider configured)[/dim]")
        return provider

    console.print("[bold]Select AI Research Provider[/bold]")
    console.print()

    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    table.add_column("#", style="dim", width=4)
    table.add_column("Provider", style="cyan")
    table.add_column("Description", style="dim")

    provider_info = {
        "perplexity": ("Perplexity", "Deep research with live web search for current data"),
        "anthropic": ("Anthropic Claude", "claude-sonnet-4-5 model, uses training data (no live web search)"),
    }

    for i, p in enumerate(available, 1):
        name, desc = provider_info.get(p, (p.title(), ""))
        table.add_row(str(i), name, desc)

    console.print(table)
    console.print()

    default_idx = available.index(settings.DEFAULT_PROVIDER) + 1
    provider_completer = WordCompleter([str(i+1) for i in range(len(available))], ignore_case=True)

    while True:
        response = prompt(
            f"Select provider (default {default_idx}): ",
            default=str(default_idx),
            completer=provider_completer,
        ).strip()

        try:
            idx = int(response)
            if 1 <= idx <= len(available):
                selected = available[idx - 1]
                name = provider_info.get(selected, (selected.title(),))[0]
                console.print(f"[green]✓[/green] Provider: {name}\n")
                return selected
            else:
                console.print(f"[red]Invalid selection. Choose 1-{len(available)}[/red]")
        except ValueError:
            console.print("[red]Please enter a number.[/red]")


def select_regions() -> List[str]:
    """Interactive region selection."""
    console.print("[bold]Select Regions[/bold]")
    console.print("Available regions:")
    console.print()

    # Display regions in a table
    table = Table(show_header=True, header_style="bold cyan", box=box.SIMPLE)
    table.add_column("#", style="dim", width=4)
    table.add_column("Region", style="cyan")
    table.add_column("Description", style="dim")

    regions_list = list(regions_data.REGIONS.keys())
    for i, region in enumerate(regions_list, 1):
        desc = regions_data.REGIONS[region].get("description", "")
        table.add_row(str(i), region, desc[:50] + "..." if len(desc) > 50 else desc)

    console.print(table)
    console.print()

    # Get user selection
    while True:
        response = prompt(
            "Enter region numbers (comma-separated, or 'all' for all regions): ",
            default="1"
        ).strip()

        if response.lower() == 'all':
            return regions_list

        try:
            indices = [int(x.strip()) for x in response.split(',')]
            selected = []
            for idx in indices:
                if 1 <= idx <= len(regions_list):
                    selected.append(regions_list[idx - 1])
                else:
                    console.print(f"[red]Invalid region number: {idx}[/red]")
                    break
            else:
                if selected:
                    return selected
        except ValueError:
            console.print("[red]Invalid input. Please enter numbers separated by commas.[/red]")


def interactive_mode():
    """Run interactive CLI mode."""
    print_welcome()

    try:
        # Step 0: Select provider (only shown if multiple available)
        step_num = 1
        if len(settings.AVAILABLE_PROVIDERS) > 1:
            console.print(f"[bold]Step {step_num}: AI Provider[/bold]")
            provider = select_provider()
            step_num += 1
        else:
            provider = settings.DEFAULT_PROVIDER

        # Get max price
        console.print(f"[bold]Step {step_num}: Maximum Median Price[/bold]")
        max_price_str = prompt(
            "Enter maximum median price (AUD): ",
            default="700000",
            validator=PriceValidator()
        )
        max_price = float(max_price_str)
        console.print(f"[green]✓[/green] Max price: ${max_price:,.0f}\n")
        step_num += 1

        # Get dwelling type
        console.print(f"[bold]Step {step_num}: Dwelling Type[/bold]")
        dwelling_types = ["house", "apartment", "townhouse"]
        dwelling_completer = WordCompleter(dwelling_types, ignore_case=True)

        while True:
            dwelling_type = prompt(
                "Enter dwelling type (house/apartment/townhouse): ",
                default="house",
                completer=dwelling_completer
            ).strip().lower()

            if dwelling_type in dwelling_types:
                console.print(f"[green]✓[/green] Dwelling type: {dwelling_type.title()}\n")
                break
            console.print("[red]Invalid dwelling type. Please choose: house, apartment, or townhouse[/red]")
        step_num += 1

        # Select regions
        console.print(f"[bold]Step {step_num}: Regions[/bold]")
        regions = select_regions()
        console.print(f"[green]✓[/green] Selected {len(regions)} region(s)\n")
        step_num += 1

        # Get number of suburbs
        console.print(f"[bold]Step {step_num}: Number of Suburbs[/bold]")
        num_suburbs_str = prompt(
            "Enter number of top suburbs to analyze: ",
            default="5",
            validator=NumSuburbsValidator()
        )
        num_suburbs = int(num_suburbs_str)
        console.print(f"[green]✓[/green] Analyzing top {num_suburbs} suburbs\n")

        # Provider display name
        provider_display = "Perplexity (Deep Research)" if provider == "perplexity" else "Anthropic Claude (claude-sonnet-4-5)"

        # Confirmation
        console.print(Panel.fit(
            f"[bold]Research Configuration[/bold]\n\n"
            f"Provider: [cyan]{provider_display}[/cyan]\n"
            f"Max Price: [cyan]${max_price:,.0f}[/cyan]\n"
            f"Dwelling: [cyan]{dwelling_type.title()}[/cyan]\n"
            f"Regions: [cyan]{', '.join(regions[:3])}{'...' if len(regions) > 3 else ''}[/cyan] ({len(regions)} total)\n"
            f"Suburbs: [cyan]{num_suburbs}[/cyan]",
            title="Confirm Settings",
            border_style="yellow"
        ))

        confirm = prompt("Proceed with research? (yes/no): ", default="yes").strip().lower()

        if confirm not in ['yes', 'y']:
            console.print("[yellow]Research cancelled.[/yellow]")
            return

        # Create user input
        from datetime import datetime
        user_input = UserInput(
            max_median_price=max_price,
            dwelling_type=dwelling_type,
            regions=regions,
            num_suburbs=num_suburbs,
            provider=provider,
            run_id=datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
            interface_mode="cli"
        )

        # Run pipeline
        console.print()
        console.print("[bold green]🚀 Starting research pipeline...[/bold green]")
        console.print()

        result = run_research_pipeline(user_input)

        # Show results
        console.print()
        if result.status == "completed":
            console.print(
                Panel.fit(
                    f"[bold green]✅ Research Complete![/bold green]\n\n"
                    f"Suburbs analyzed: [cyan]{len(result.suburbs)}[/cyan]\n"
                    f"Output directory: [cyan]{result.output_dir}[/cyan]\n\n"
                    f"[dim]Open the report:[/dim]\n"
                    f"[bold cyan]file://{result.output_dir.absolute()}/index.html[/bold cyan]",
                    title="Success",
                    border_style="green"
                )
            )

            # Offer to open report
            open_report = prompt("Open report in browser? (yes/no): ", default="yes").strip().lower()
            if open_report in ['yes', 'y']:
                import webbrowser
                webbrowser.open(f"file://{result.output_dir.absolute()}/index.html")
                console.print("[green]✓[/green] Opened in browser")

            # Offer PDF export
            export_pdf = prompt("Generate PDF report? (yes/no): ", default="no").strip().lower()
            if export_pdf in ['yes', 'y']:
                try:
                    from reporting.exports import generate_pdf_export
                    with console.status("[bold cyan]Generating PDF...[/bold cyan]"):
                        pdf_path = generate_pdf_export(result, result.output_dir)
                    console.print(f"[green]✓[/green] PDF saved: {pdf_path}")
                except Exception as e:
                    console.print(f"[red]PDF export failed:[/red] {e}")

            # Offer Excel export
            export_xlsx = prompt("Generate Excel report? (yes/no): ", default="no").strip().lower()
            if export_xlsx in ['yes', 'y']:
                try:
                    from reporting.exports import generate_excel_export
                    with console.status("[bold cyan]Generating Excel...[/bold cyan]"):
                        xlsx_path = generate_excel_export(result, result.output_dir)
                    console.print(f"[green]✓[/green] Excel saved: {xlsx_path}")
                except Exception as e:
                    console.print(f"[red]Excel export failed:[/red] {e}")
        else:
            console.print(
                Panel.fit(
                    f"[bold red]❌ Research Failed[/bold red]\n\n"
                    f"Status: {result.status}\n"
                    f"Error: {result.error_message or 'Unknown error'}",
                    title="Error",
                    border_style="red"
                )
            )

    except KeyboardInterrupt:
        console.print("\n\n[yellow]⚠️  Cancelled by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        import traceback
        console.print("[dim]" + traceback.format_exc() + "[/dim]")
        sys.exit(1)


def quick_mode():
    """Quick mode with minimal prompts."""
    print_welcome()

    console.print("[bold]Quick Setup Mode[/bold]")
    console.print("Using default settings with custom price and suburbs...\n")

    try:
        # Quick inputs
        max_price_str = prompt("Max price (default 700000): ", default="700000")
        max_price = float(max_price_str)

        num_suburbs_str = prompt("Number of suburbs (default 5): ", default="5")
        num_suburbs = int(num_suburbs_str)

        provider = settings.DEFAULT_PROVIDER
        provider_display = "Perplexity" if provider == "perplexity" else "Anthropic Claude"

        console.print(f"\n[green]✓[/green] Configuration set")
        console.print(f"  Provider: {provider_display}")
        console.print(f"  Price: ${max_price:,.0f}")
        console.print(f"  Type: House")
        console.print(f"  Region: South East Queensland")
        console.print(f"  Suburbs: {num_suburbs}\n")

        # Create input
        from datetime import datetime
        user_input = UserInput(
            max_median_price=max_price,
            dwelling_type="house",
            regions=["South East Queensland"],
            num_suburbs=num_suburbs,
            provider=provider,
            run_id=datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
            interface_mode="cli"
        )

        # Run
        console.print("[bold green]🚀 Starting research...[/bold green]\n")
        result = run_research_pipeline(user_input)

        # Results
        if result.status == "completed":
            console.print(f"\n[bold green]✅ Complete![/bold green] {len(result.suburbs)} suburbs analyzed")
            console.print(f"📁 {result.output_dir}/index.html")
        else:
            console.print(f"\n[bold red]❌ Failed:[/bold red] {result.error_message}")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Cancelled[/yellow]")
        sys.exit(0)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Interactive CLI for Australian Property Research",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode with minimal prompts"
    )

    args = parser.parse_args()

    if args.quick:
        quick_mode()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
