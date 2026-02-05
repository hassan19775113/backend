"""
Management command to set up production database
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Set up production database with migrations and admin user'

    def handle(self, *args, **options):
        self.stdout.write('Running migrations...')
        call_command('migrate', '--noinput')
        
        User = get_user_model()
        
        if not User.objects.filter(username='admin').exists():
            self.stdout.write('Creating admin user...')
            User.objects.create_superuser(
                username='admin',
                email='admin@praxiapp.com',
                password='praxiapp2026!Admin'
            )
            self.stdout.write(self.style.SUCCESS('Admin user created!'))
            self.stdout.write(f'Username: admin')
            self.stdout.write(f'Password: praxiapp2026!Admin')
        else:
            self.stdout.write('Admin user already exists')
        
        self.stdout.write(self.style.SUCCESS('Setup completed!'))
