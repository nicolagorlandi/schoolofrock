#ricorsione per costruzione menù...
def build_menu_tree(items):
    lookup = {item.id: item for item in items}

    # inizializza child_list per tutti
    for item in items:
        item.child_list = []

    # collega ogni item al suo parent
    for item in items:
        if item.parent_id:
            parent = lookup.get(item.parent_id)
            if parent:
                parent.child_list.append(item)

    # restituisce solo i nodi radice
    return [item for item in items if item.parent_id is None]