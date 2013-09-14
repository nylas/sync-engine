'use strict';
var app = angular.module('InboxApp.services');


/*  Notification API servie  */
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

            windowSize.leftColHeight = windowSize.mainHeight - 15;
            windowSize.leftMessageListHeight = windowSize.mainHeight - $('.leftHeader').outerHeight(true) - $('.leftFooter').outerHeight(true) - 15;

            windowSize.rightContentWidth = windowSize.width - $('.leftcol').width();

            windowSize.contentBodyHeight = windowSize.mainHeight; //  - $('.contentHead').outerHeight(true) - $('#reply_box').outerHeight(true) + 10;

            windowSize.contentBodyWidth = $('.contentBody').width();

            windowSize.updateSizes();
        },
        updateSizes: function() {
            $('#main').css('height', windowSize.mainHeight + 'px');
            $('.leftcol').css('height', windowSize.leftColHeight + 'px');
            $('.messagelist').css('height', windowSize.leftMessageListHeight + 'px');

            $('.content').css('width', windowSize.rightContentWidth + 'px');

            $('#reply_box').css('width', windowSize.rightContentWidth - 20.0 + 'px'); // TOFIX DEBUG HACK

            $('.contentBody').css('width', windowSize.rightContentWidth + 'px');
            $('.contentBody').css('height', (windowSize.contentBodyHeight) + 'px');

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