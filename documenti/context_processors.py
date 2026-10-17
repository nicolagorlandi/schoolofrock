from documenti.models import Causdocu
from documenti.cart import Cart
from PaNet1Project.settings import CCATCLI, CCATFOR
from .models import MenuItem
from .menu_utils import build_menu_tree
from Corsi.permissions import is_insegnante

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
    insegnante = is_insegnante(request.user)
    if insegnante:
        allowed_urls = {'corsi:calendario-lezioni', 'logout'}

        def retain_allowed_items(item):
            children = getattr(item, 'child_list', [])
            item.child_list = [
                child for child in children
                if retain_allowed_items(child)
            ]
            return (
                item.url_name in allowed_urls and not item.tipoDocumento
            ) or bool(item.child_list)

        menu_tree = [
            item for item in menu_tree if retain_allowed_items(item)
        ]
    return {'MENU_TREE': menu_tree, 'is_insegnante': insegnante}
