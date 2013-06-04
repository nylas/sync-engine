
/* These are actually services */
var app = angular.module('InboxApp.models', []);

/* Using this strategy:
  http://stackoverflow.com/questions/13762228/confused-about-service-vs-factory
  */


/* Thread factory that provides a constructor so we can do something like:

var myThread = new Thread(some_thread_id, array_of_msg_ids);

This object type should only be accessible if it's injected. 

Still unknown: is every object created this way still a singleton?
They shouldn't be because the actual constructor is returning a new one. 

Probably calling Thread.whatever() will be a class function, whereas 
instance.whatever() will be one of the methods defined through prototype

 */



app.factory('IBThread', function ($injector) {

    function IBThreadObject($rootScope, data) {
        this.$rootScope = $rootScope;
        // TODO handle default values here or when data=none
        this.message_ids = data.message_ids;
        this.thread_id = data.thread_id;
        this.labels = data.labels;
    }


    return function(data) {
      return $injector.instantiate(
        IBThreadObject, {data:data});
    };
});



app.factory('IBMessage', function ($injector)
{
    function IBMessageObject($rootScope, data) {
        this.$rootScope = $rootScope;
        // Do handle data=none values
        this.message_id = data.message_id;
        this.thread_id = data.thread_id;
        this.labels = data.labels;
        this.uid = data.uid;
        this.to_contacts = data.to_contacts;
        this.from_contacts = data.from_contacts[0];
        this.subject = data.subject;
        this.message_parts = data.message_parts;
        this.attachments = data.attachments;

        console.log(this.message_parts);

        // the zero sets to epoch, then add seconds
        // var d = new Date(0);

        this.date = new Date(data.date * 1000)



        var gravatar_size = 25;
        var theEmail = this.from_contacts[2] + '@' + this.from_contacts[3];
        this.gravatar_url = "http://www.gravatar.com/avatar/" +
                        md5( theEmail.toLowerCase() )+ "?" +
                        'd=mm&' +
                        's=' + encodeURIComponent(gravatar_size);


        console.log("to contacts");
        console.log(data.to_contacts);

        if (this.to_contacts && this.to_contacts.length > 0) {

            var to_list;
            if (this.to_contacts[0][0] ) {
                to_list = this.to_contacts[0][0];
            } else {
                to_list = this.to_contacts[0][2] + '@' + this.to_contacts[0][3];
            }

            for (var i = 1; i< this.to_contacts.length; i++) {
                var c = this.to_contacts[i];
                var nameToShow;
                if (c[0]) {
                    nameToShow = c[0];
                } else {
                    nameToShow = c[2] + '@' + c[3];
                }
                to_list = to_list + ', ' + nameToShow;
            }
            this.contactDisplayList = to_list;
        } else {
            this.contactDisplayList = 'Unknown sender';
        }




    }

    IBMessageObject.prototype.printDate = function() {
        // var curr_date = this.date.getDate();
        // var curr_month = this.date.getMonth() + 1; //Months are zero based
        // var curr_year = this.date.getFullYear();
        // return curr_date + "-" + curr_month + "-" + curr_year;

        return this.date.toLocaleString();
    }

    return function(data) {
      return $injector.instantiate(
        IBMessageObject, {data:data});
    };
});




app.factory('IBContact', function ($injector) {

    var IBObject = function($rootScope, data) {
        this.$rootScope = $rootScope;
        // Break serialized data out into object
        this.firstname = data.firstname;
        this.lastname = data.lastname;
        this.emai = data.email;
    };

    IBObject.prototype.gravatarURL = function (size) {
        // TODO pull this size into the css somewhere I think.
        size = typeof seize !== 'undefined' ? size : 25; // Default size.
        var gravatar_url = "http://www.gravatar.com/avatar/" +
                        md5( this.email.toLowerCase() )+ "?" +
                        'd=mm&' +
                        's=' + encodeURIComponent(size);
         return gravatar_url;
    };
    return function(name) {
      return $injector.instantiate(
        IBObject, { data: data });
    };
});





