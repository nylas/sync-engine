
/* These are actually services */
var app = angular.module('InboxApp.models', []);

/* Using this strategy:
  http://stackoverflow.com/questions/13762228/confused-about-service-vs-factory
  */

/* Thread factory that provides a constructor so we can do something like:
var myThread = new Thread(some_thread_id, array_of_msg_ids);
This object type should only be accessible if it's injected.
Probably calling Thread.whatever() will be a class function, whereas
instance.whatever() will be one of the methods defined through prototype

Here's an explanation of how all of this reduces to factories.
https://groups.google.com/forum/#!msg/angular/56sdORWEoqg/b8hdPskxZXsJ

 */



app.factory('IBThread', function ($injector) {

    function IBThreadObject($rootScope) {
        // TODO assert that these are the right message object types
        this.messages = [];
        this.$rootScope = $rootScope;
    }


    IBThreadObject.prototype.displayFrom = function() {
        return 'Joe Schmo';
    };

    IBThreadObject.prototype.last = function() {
        return this.messages[this.messages.length - 1];
    };



    return function(messages) {
        // This is based on $injector.instantiate
        var Type = IBThreadObject;
        // var locals = {messages:messages};
        var locals = {};

        var IBThread = function() {};
        var instance;
        var returnedValue;

        // Check if Type is annotated and use just the given function at n-1 as parameter
        // e.g. someModule.factory('greeter', ['$window', function(renamed$window) {}]);
        IBThread.prototype = (angular.isArray(Type) ? Type[Type.length - 1] : Type).prototype;
        instance = new IBThreadObject();

        returnedValue = $injector.invoke(Type, instance, locals);
        return angular.isObject(returnedValue) ? returnedValue : instance;

    };

});



app.factory('IBMessageMeta', function ($injector)
{
    function IBMessageMetaObject($rootScope, data) {
        this.$rootScope = $rootScope;

        // Propogate fields to the object
        for (var key in data) {
            if (self.hasOwnProperty(key)) {
                console.log(key + " -> " + p[key]);
            }
            this[key] = data[key];
        }
        // Fix the date
        this.date = new Date(data.date.$date);

        this.parts = {};


        var gravatar_size = 25;
        var theEmail = this.from[0][2] + '@' + this.from[0][3];
        this.gravatar_url = "https://www.gravatar.com/avatar/" +
                        md5( theEmail.toLowerCase() )+ "?" +
                        'd=mm&' +
                        's=' + encodeURIComponent(gravatar_size);


        if (this.to && this.to.length > 0) {

            var to_list;
            if (this.to[0][0] ) {
                to_list = this.to[0][0];
            } else {
                to_list = this.to[0][2] + '@' + this.to[0][3];
            }


            for (var i = 1; i< this.to.length; i++) {
                var c = this.to[i];
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


    IBMessageMetaObject.prototype.printDate = function() {
        // var curr_date = this.date.getDate();
        // var curr_month = this.date.getMonth() + 1; //Months are zero based
        // var curr_year = this.date.getFullYear();
        // return curr_date + "-" + curr_month + "-" + curr_year;

        return this.date.toLocaleString();
    };


    return function(data) {
        // This is based on $injector.instantiate
        var Type = IBMessageMetaObject;
        var locals = {data:data};

        var IBMessageMeta = function() {};
        var instance;
        var returnedValue;

        // Check if Type is annotated and use just the given function at n-1 as parameter
        // e.g. someModule.factory('greeter', ['$window', function(renamed$window) {}]);
        IBMessageMeta.prototype = (angular.isArray(Type) ? Type[Type.length - 1] : Type).prototype;
        instance = new IBMessageMeta();

        returnedValue = $injector.invoke(Type, instance, locals);
        return angular.isObject(returnedValue) ? returnedValue : instance;

    };
});



app.factory('IBMessagePart', function ($injector)
{
    function IBMessagePartObject($rootScope, data) {
        this.$rootScope = $rootScope;

        // Propogate fields to the object
        for (var key in data) {
            if (self.hasOwnProperty(key)) {
                console.log(key + " -> " + p[key]);
            }
            this[key] = data[key];
        }
    }

    IBMessagePartObject.prototype.toString = function() {
        return 'some string mame...';
    };



    return function(data) {
        // This is based on $injector.instantiate
        var Type = IBMessagePartObject;
        var locals = {data:data};

        var IBMessagePart = function() {};
        var instance;
        var returnedValue;

        // Check if Type is annotated and use just the given function at n-1 as parameter
        // e.g. someModule.factory('greeter', ['$window', function(renamed$window) {}]);
        IBMessagePart.prototype = (angular.isArray(Type) ? Type[Type.length - 1] : Type).prototype;
        instance = new IBMessagePart();

        returnedValue = $injector.invoke(Type, instance, locals);
        return angular.isObject(returnedValue) ? returnedValue : instance;

    };
});






app.factory('IBContact', function ($injector) {

    var IBObject = function($rootScope, data) {
        this.$rootScope = $rootScope;
        // Break serialized data out into object
        this.firstname = data.firstname;
        this.lastname = data.lastname;
        this.email = data.email;
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





