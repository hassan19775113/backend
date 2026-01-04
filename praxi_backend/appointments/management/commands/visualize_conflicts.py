"""
Management Command: visualize_conflicts

Generates text-based visualizations of scheduling conflicts.

Usage:
    python manage.py visualize_conflicts
    python manage.py visualize_conflicts --seed 42
    python manage.py visualize_conflicts --section heatmap
    python manage.py visualize_conflicts --output conflicts.txt

==============================================================================
"""

import sys

from django.core.management.base import BaseCommand

from praxi_backend.appointments.services.scheduling_visualization import (
    VisualizationContext,
    create_conflict_table,
    create_doctor_heatmap,
    create_grouped_tables,
    create_hourly_heatmap,
    create_room_heatmap,
    create_summary,
    generate_conflict_visualization,
    visualize_absences,
    visualize_doctor_conflicts,
    visualize_edge_cases,
    visualize_room_conflicts,
    visualize_working_hours,
)


class Command(BaseCommand):
    help = "Generate text-based visualizations of scheduling conflicts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Random seed for reproducible test data",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default=None,
            help="Write output to file instead of stdout",
        )
        parser.add_argument(
            "--section",
            "-s",
            type=str,
            choices=[
                'all', 'doctor', 'room', 'table', 'groups',
                'heatmap', 'doctor-heatmap', 'room-heatmap',
                'absences', 'working-hours', 'edge-cases', 'summary'
            ],
            default='all',
            help="Generate only specific section",
        )

    def handle(self, *args, **options):
        seed = options.get("seed")
        output_file = options.get("output")
        section = options.get("section")

        self.stdout.write(self.style.NOTICE("\nGenerating conflict visualization..."))
        self.stdout.write(f"Seed: {seed or 'random'}")
        self.stdout.write(f"Section: {section}\n")

        try:
            if section == 'all':
                output = generate_conflict_visualization(seed=seed)
            else:
                ctx = VisualizationContext(seed=seed)
                ctx.setup()
                
                section_map = {
                    'doctor': lambda: visualize_doctor_conflicts(ctx),
                    'room': lambda: visualize_room_conflicts(ctx),
                    'table': lambda: create_conflict_table(ctx),
                    'groups': lambda: create_grouped_tables(ctx),
                    'heatmap': lambda: create_hourly_heatmap(ctx),
                    'doctor-heatmap': lambda: create_doctor_heatmap(ctx),
                    'room-heatmap': lambda: create_room_heatmap(ctx),
                    'absences': lambda: visualize_absences(ctx),
                    'working-hours': lambda: visualize_working_hours(ctx),
                    'edge-cases': lambda: visualize_edge_cases(),
                    'summary': lambda: create_summary(ctx),
                }
                
                output = section_map[section]()

            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(output)
                self.stdout.write(
                    self.style.SUCCESS(f"\n✓ Visualization written to: {output_file}")
                )
            else:
                self.stdout.write("\n" + output)

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error: {e}"))
            import traceback
            traceback.print_exc()
            sys.exit(1)
