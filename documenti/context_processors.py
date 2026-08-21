from documenti.models import Causdocu
from documenti.cart import Cart
from PaNet1Project.settings import CCATCLI, CCATFOR

# aggiunge a tutti i template le causali
def causali(request):
    if request.user.is_authenticated:
        return {'causali':Causdocu.objects.all().order_by('-CD_CICLO'),
                'itemInCart':Cart(request),
                'CCATCLI':CCATCLI,
                'CCATFOR':CCATFOR            
                }
    else:
        return {}