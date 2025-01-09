from .models import Articoli

# classe per la gestione del carello nella session!
class Cart():
    def __init__(self,request):
        self.session=request.session

        cart = self.session.get('session_key')

        if 'session_key' not in self.session:
            cart = self.session['session_key']={}
        
        self.cart=cart

    # aggiunge un articolo al carrello    
    def add(self,product,quantity):
        product_id=product.ARCODICE
        product_qty=int(quantity)
        if product_id in self.cart:
            self.cart[product_id] = product_qty
        else:
            self.cart[product_id] = product_qty
        
        self.session.modified = True

    # rimuove un articolo dal carrello    
    def remove(self,product):
        product_id=product.ARCODICE
        self.cart.pop(product.ARCODICE)
        self.session.modified = True    

    # svuoto il carrello
    def removeAll(self):
        cart = self.session['session_key']={}
        self.cart=cart
    
    def getProductQty(self,product):
        if product.ARCODICE in self.cart:
            return self.cart[product.ARCODICE]
        else:
            return 0
            

    # Ritorna il numero di articoli nel carrello (non le quantità)
    def count(self):
        return len(self.cart)
    
    # ritorna gli articoli nel carrello
    def getProducts(self):
        prod_id=self.cart.keys()
        articoli = Articoli.objects.filter(ARCODICE__in=prod_id)
        return articoli
    
    # ritorna l'elenco delle quantita
    def getQuants(self):        
        return self.cart 

    # ritorna il totale del carrello..
    def getCartTotal(self):        
        product_ids = self.cart.keys()
        # ricerco gli id all'interno del data model per recuperare i prezzi..
        prodotti = Articoli.objects.filter(ARCODICE__in=product_ids)
        # recupero le quantita
        quantities =self.cart

        total = 0
        for keys,value in quantities.items():
            for prodotto in prodotti:
                if prodotto.ARCODICE==keys:
                    total = total + (prodotto.ARPREZZO*value)
                    break

        return total                
                    