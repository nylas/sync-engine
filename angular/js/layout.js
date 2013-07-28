var windowSize = {
height: 0,
width: 0,
headersHeight: 0,
mainHeight: 0,
contentBodyHeight: 0,
contentBodyWidth: 0,
leftNavHeight: 0,
contentDetailsWidth: 0,
setDimensions: function(){
	windowSize.height = $('body').height();
	windowSize.width = $('body').width();

	windowSize.headersHeight = $('#header').height();
	windowSize.mainHeight = windowSize.height - windowSize.headersHeight;

	windowSize.leftMessageListHeight = windowSize.mainHeight - $('.leftHeader').outerHeight(includeMargin=true) 
                                                               - $('.leftFooter').outerHeight(includeMargin=true);

      windowSize.rightContentWidth = windowSize.width - $('.leftcol').width();

      windowSize.contentBodyHeight = windowSize.mainHeight - $('.contentHead').outerHeight(includeMargin=true) 
                                                           - $('.contentFoot').outerHeight(includeMargin=true);

      windowSize.contentBodyWidth = $('.contentBody').width();

	windowSize.updateSizes();
},
updateSizes: function(){
	$('#main').css('height',windowSize.mainHeight+'px');

	$('.messagelist').css('height',windowSize.leftMessageListHeight+'px');

      $('.content').css('width',windowSize.rightContentWidth+'px');

      $('.contentBody').css('width', windowSize.rightContentWidth+'px');
      $('.contentBody').css('height',(windowSize.contentBodyHeight)+'px');

},
init: function(){
	if($('#main').length){
		windowSize.setDimensions();
		$(window).resize(function() {
			windowSize.setDimensions();                
		});
	}
}
};
$(document).ready(function(){
windowSize.init();
});
