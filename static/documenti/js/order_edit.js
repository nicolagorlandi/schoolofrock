    function cambioProdotto(valore,caller){
        $.ajax({
            url: '/doc/ajax/leggiPrezzoDescrizioneArticolo/',
            data: {
              'articoloId': valore,
              'name':caller.name 
            },
            dataType: 'json',
            success: function (data) {
                $( "input[name$='"+data.prefisso+"DODESART']" )[0].value=data.ARDESCRI;                
                $( "input[name$='"+data.prefisso+"DOPREZZO']" )[0].value=data.ARPREZZO;
                // se quantita a 0 la metto a 1
                var qta = $( "input[name$='"+data.prefisso+"DOQTAUM1']" )[0].value;
                if (qta==="0") 
                {
                    $( "input[name$='"+data.prefisso+"DOQTAUM1']" )[0].value=1;
                }   
                $( "textarea[name$='"+data.prefisso+"DODESSUP']" )[0].value=data.ARDESSUP;
            }
          });        
    }
    
    // al cambio di qta e prezzo aggiorno il totale ordine...TODO
        
    // crea una nuova form per aggiungere un nuovo rigo.
    (function($) {
        $('#add-form').click(function() {
            var index = $('#id_ord_dett_set-TOTAL_FORMS').val()
            var rigaVuota =  $('#id_ord_dett_set-__prefix__-DELETE').parents('tr')
            if(rigaVuota)
            {
                var newTable = rigaVuota.clone()
                newTable.find(':input').each(function() {
                    for (attr of ['name', 'id'])
                        $(this).attr(
                            attr,
                            $(this).attr(attr).replace('__prefix__', index)
                        )
                })
                newTable.insertBefore(rigaVuota)
                $('#id_ord_dett_set-TOTAL_FORMS').val(
                    parseInt($('#id_ord_dett_set-TOTAL_FORMS').val()) + 1
                )
                newTable.slideDown()
            }

        })
    })($)