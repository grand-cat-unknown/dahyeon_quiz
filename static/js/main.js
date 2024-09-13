// static/js/main.js
// Adjust button sizing for touch interfaces
if ('ontouchstart' in window) {
    var buttons = document.getElementsByTagName('button');
    for (var i = 0; i < buttons.length; i++) {
        buttons[i].style.minHeight = '44px';
    }
}