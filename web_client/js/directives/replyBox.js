var app = angular.module('InboxApp.directives');


app.directive("replybox", function() {
    return {

        restrict: 'E',
        transclude: true,
        scope: {
            sendButtonAction: '&sendButtonAction'
        }, // Two-way binding to message object
        controller: function($scope, $element, $attrs, $transclude) {

            // TODO
        },


        // <div ng-file-upload="/file_upload"
        // data-complete='uploadComplete()'
        //  data-error="uploadError()"></div>


        // #drop:hover, #drop.active {
        //     border: 2px dashed #08c;
        //     color: #08c;
        // }

        // * textarea {
        // *  resize: none;
        // *  word-wrap: break-word;
        // *  transition: 0.05s;
        // *  -moz-transition: 0.05s;
        // *  -webkit-transition: 0.05s;
        // *  -o-transition: 0.05s;
        // * }


        templateUrl: 'views/replyBox.html',

        link: function(scope, elem, attrs, ctrl) {


            // TODO resize reply box as you type stuff in it
            // var obj = elem.find('#reply_textbox');
            // var update = function() {
            //     var scrollable = $('#right-scrollable');

            //     // scrollable.animate({
            //     //     scrollTop: 9999999
            //     // }, 'slow');


            //     scrollable.scrollTop = 9999999;
            //     // x = 0; //horizontal coord
            //     // y = document.height; //vertical coord
            //     // window.scroll(x, y);
            // };
            // obj.bind('keyup keydown keypress change', update);
            // // update();

            scope.sendButtonHandler = function() {
                var textbox = elem.find('#reply_textbox');

                scope.sendButtonAction({
                    message_text: textbox.html()
                });
            };

            var upload_file_button = elem.find('#add_file_button');
            upload_file_button.bind('click', function() {
                var input = elem.find('input')[0];
                input.click();
            });



            // Initialize the jQuery File Upload plugin
            $('#file-upload').fileupload({
                // This element will accept file drag/drop uploading
                dropZone: $('#drop'),

                // This function is called when a file is added to the queue;
                // either via the browse button, or via drag/drop:
                add: function(e, data) {
                    // var tpl = $('<li class="working"><input type="text" value="0" data-width="48" data-height="48"'+
                    //   ' data-fgColor="#0788a5" data-readOnly="1" data-bgColor="#3e4043" /><p></p><span></span></li>');

                    // // Append the file name and file size
                    // tpl.find('p').text(data.files[0].name)
                    //   .append('<i>' + $filter.humanBytes(data.files[0].size) + '</i>');

                    // // Add the HTML to the UL element
                    // data.context = tpl.appendTo(ul);

                    // // Initialize the knob plugin
                    // tpl.find('input').knob();

                    // // Listen for clicks on the cancel icon
                    // tpl.find('span').click(function(){
                    //   if(tpl.hasClass('working')){
                    //     jqXHR.abort();
                    //   }

                    //   tpl.fadeOut(function(){
                    //     tpl.remove();
                    //   });
                    // });

                    // Automatically upload the file once it is added to the queue
                    var jqXHR = data.submit();
                },

                done: function(e, data) {

                    scope.$apply(function(s) {
                        // Completion function handler
                        s.$eval(attrs.complete);

                        console.log("Done! With hash: " + data.result);

                    });
                },

                progress: function(e, data) {
                    // Calculate the completion percentage of the upload
                    var progress = parseInt(data.loaded / data.total * 100, 10);

                    // Update the hidden input field and trigger a change
                    // so that the jQuery knob plugin knows to update the dial

                    // data.context.find('input').val(progress).change();

                    console.log("Uploaded: " + progress);

                    if (progress == 100) {
                        // data.context.removeClass('working');
                        console.log("Working...");
                    }

                },

                fail: function(e, data) {
                    scope.$apply(function(s) {

                        console.log("Error uploading...");
                        console.log(e);
                        console.log(data);

                        s.$eval(attrs.error);
                    });

                    // data.context.addClass('error');
                }
            });


            // Prevent the default action when a file is dropped on the window
            $(document).on('dragover', function(e) {
                e.preventDefault();
                $('#drop').addClass('active');
            });

            $(document).on('drop dragleave', function(e) {
                e.preventDefault();
                $('#drop').removeClass('active');
            });


        } // end link

    };
});


