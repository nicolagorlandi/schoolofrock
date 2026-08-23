from documenti.models import Causdocu
from documenti.cart import Cart
from PaNet1Project.settings import CCATCLI, CCATFOR
from .models import MenuItem
from .menu_utils import build_menu_tree

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


# costruisce il menù partendo dal database
def menu_processor(request):
    items = MenuItem.objects.filter(visible=True)
    menu_tree = build_menu_tree(items)
    return {"MENU_TREE": menu_tree}
