from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging

logger = logging.getLogger(__name__)

def health_check(request):
    """Health check endpoint"""
    return JsonResponse({
        "status": "healthy",
        "service": "Sanchalak Telegram Bot",
        "version": "1.0.0"
    })

@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request):
    """Telegram webhook endpoint (if needed for webhook mode)"""
    try:
        data = json.loads(request.body)
        # Process telegram update here if using webhook mode
        logger.info(f"Received telegram update: {data}")
        
        return JsonResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"Error processing telegram webhook: {e}")
        return JsonResponse({"error": str(e)}, status=500) 