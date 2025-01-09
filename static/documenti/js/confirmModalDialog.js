// ricerca tutti i control con la classe confirm-modal
$(document).on('click', '.confirm-modal', function () {
  // passo l'url da eseguire alla conferma (usato sotto)
  $("#confirmButtonModal").attr("caller-id", $(this).data("recordid"));
  // recupero la frase da riportare
  var msgText = $(this).data('msgtext');
  // para con il contenuto del messaggio
  var paragraph = document.getElementById("modalMessagePara");
  paragraph.textContent = msgText;
  
});

$(document).on('click', '#confirmButtonModal', function () {
  var caller = $("#confirmButtonModal").attr("caller-id");
  var urlPulsante = $('a[data-recordid="'+caller+'"]')[0].href
  window.location = urlPulsante;
});


