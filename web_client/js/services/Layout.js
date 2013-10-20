'use strict';
var app = angular.module('InboxApp.services');


app.factory('layout', function() {

    // This should all be done on doc load
    var windowSize = {
        height: 0,
        width: 0,
        headersHeight: 0,
        mainHeight: 0,
        contentBodyHeight: 0,
        contentBodyWidth: 0,
        leftNavHeight: 0,
        contentDetailsWidth: 0,
        setDimensions: function() {
            windowSize.height = $('body').height();
            windowSize.width = $('body').width();

            windowSize.headersHeight = $('#header').height();
            windowSize.mainHeight = windowSize.height - windowSize.headersHeight;

            windowSize.leftPaneHeight = windowSize.mainHeight;
            windowSize.leftMessageListHeight = windowSize.mainHeight - $('.header_left').outerHeight(true) - $('.footer_left').outerHeight(true);

            windowSize.rightContentWidth = windowSize.width - $('.sidebar').width() - $('.left_pane').width();

            windowSize.contentBodyHeight = windowSize.mainHeight  - $('.action_bar_top').outerHeight(true);

            windowSize.contentBodyWidth = $('.right_panel_container').width();

            windowSize.updateSizes();
        },
        updateSizes: function() {
            $('#main').css('height', windowSize.mainHeight + 'px');
            $('.left_pane').css('height', windowSize.leftPaneHeight + 'px');
            $('.messagelist').css('height', windowSize.leftMessageListHeight + 'px');

            $('.panel_right_content').css('width', windowSize.rightContentWidth + 'px');

            $('.panel_right').css('width', windowSize.rightContentWidth + 'px');


            $('.right_panel_container').css('width', windowSize.rightContentWidth + 'px');
            $('.right_panel_container').css('height', (windowSize.contentBodyHeight) + 'px');

        },
        init: function() {
            if ($('#main').length) {
                windowSize.setDimensions();
                $(window).resize(function() {
                    windowSize.setDimensions();
                });
            }
        }
    };
    $(document).ready(function() {
        windowSize.init();
    });


    return {
        reflow: function() {
            windowSize.setDimensions();
        },

    }
});
