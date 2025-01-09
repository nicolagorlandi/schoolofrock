from documenti.models import Causdocu
from documenti.cart import Cart

# aggiunge a tutti i template le causali
def causali(request):
    if request.user.is_authenticated:
        return {'causali':Causdocu.objects.all().order_by('-CD_CICLO'),
                'itemInCart':Cart(request)            
                }
    else:
        return {}