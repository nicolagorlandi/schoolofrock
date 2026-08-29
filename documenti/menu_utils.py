#ricorsione per costruzione menù...
from documenti.models import Doctipba, MenuItem


def build_menu_tree(items):
    lookup = {item.id: item for item in items}

    # inizializza child_list per tutti
    for item in items:
        item.child_list = []

    # dopo aver costruito la struttura di base applico doctiba
    for item in items:
            # se non ha parentId potrebbe avere valorizzato il campo ciclo
            # per cui genero in automatico le voci id menù in base a doctipba
            if item.tipoDocumento:
                documenti = Doctipba.objects.filter(DT_CICLO=item.tipoDocumento).order_by('DTORDINE')

                for documento in documenti:
                    # creo un nuovo item e lo aggiungo 
                    newitem = MenuItem( label=documento.DTTITOLO, url_name = 'documenti',tipoDocumento =documento.DTCODICE ,parent = item  )
                    item.child_list.append(newitem)

    # collega ogni item al suo parent in coda ai documenti..
    for item in items:
        if item.parent_id:
            parent = lookup.get(item.parent_id)
            if parent:
                parent.child_list.append(item)

    # restituisce solo i nodi radice
    return [item for item in items if item.parent_id is None]