#!/usr/bin/env python3
"""
Quick demo of the Australian Property Research application.
Runs a small test with 2 suburbs to validate the complete pipeline.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from models.inputs import UserInput
from app import run_research_pipeline


def main():
    print("\n" + "="*80)
    print("🎯 QUICK DEMO - Australian Property Research")
    print("="*80)
    print("\nThis demo will:")
    print("  1. Discover affordable suburbs in South East Queensland")
    print("  2. Research 2 suburbs in detail (using Perplexity)")
    print("  3. Rank them by growth potential")
    print("  4. Generate professional HTML reports with charts")
    print("\n⏱️  Expected time: 3-5 minutes (Perplexity deep research)")
    print("\n" + "="*80)

    response = input("\nProceed with demo? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Demo cancelled.")
        return

    # Create demo input
    user_input = UserInput(
        max_median_price=650000,  # Affordable threshold
        dwelling_type="house",
        regions=["South East Queensland"],
        num_suburbs=2,  # Small number for quick demo
        interface_mode="cli"
    )

    # Run the pipeline
    result = run_research_pipeline(user_input)

    # Show result
    if result.status == "completed":
        print("\n" + "="*80)
        print("🎉 DEMO COMPLETED SUCCESSFULLY!")
        print("="*80)
        print(f"\n✅ Generated reports for {len(result.suburbs)} suburbs")
        print(f"📁 Location: {result.output_dir}")
        print(f"\n🌐 To view the reports, open:")
        print(f"   file://{result.output_dir.absolute()}/index.html")
        print("\nOr run:")
        print(f"   open {result.output_dir}/index.html")
        print("\n" + "="*80)
    else:
        print("\n" + "="*80)
        print(f"❌ Demo failed: {result.error_message or result.status}")
        print("="*80)


if __name__ == "__main__":
    main()
