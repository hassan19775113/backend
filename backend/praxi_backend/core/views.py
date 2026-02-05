"""
Temporary setup view for Vercel deployment
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.management import call_command
from io import StringIO
import os


@require_http_methods(["GET"])
def setup_database(request):
    """
    Temporary endpoint to run migrations and create admin user.
    Only works with the correct secret key.
    
    Usage: GET /setup/?secret=YOUR_SECRET
    
    ⚠️ DELETE THIS VIEW AFTER FIRST USE!
    """
    # Check secret key
    secret = request.GET.get('secret')
    expected_secret = os.environ.get('SETUP_SECRET', 'setup-praxiapp-2026')
    
    if secret != expected_secret:
        return JsonResponse({
            'error': 'Unauthorized',
            'message': 'Invalid secret key'
        }, status=403)
    
    try:
        # Capture command output
        out = StringIO()
        
        # Run the setup command
        call_command('setup_production', stdout=out)
        
        output = out.getvalue()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Database setup completed',
            'output': output,
            'credentials': {
                'username': 'admin',
                'password': 'praxiapp2026!Admin',
                'note': 'CHANGE THIS PASSWORD IMMEDIATELY AFTER LOGIN!'
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
