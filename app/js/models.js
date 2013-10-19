
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


app.factory('IBContact', function ($injector) {
    /*
    Contact fields:
    - id (sqlalchemy)
    - email
    - name
    - google_id
    - updated_at
    - created_at

    */


    function IBContactObject($rootScope, data) {
        this.$rootScope = $rootScope;
        // Propogate fields to the object
        for (var key in data) {
            if (self.hasOwnProperty(key)) {
                console.log('Overwriting: ' + key + " -> " + data[key]);
            }
            this[key] = data[key];
        }

        if (this.name) {
            var s = this.name.split(' ');

            this.firstName = s[0];
            this.lastName = s[s.length - 1];
        }
     }

    // IBThreadObject.prototype.firstName = function() {
    //     return this.name.split(' ')[0];
    // };


    // IBObject.prototype.gravatarURL = function (size) {
    //     // TODO pull this size into the css somewhere I think.
    //     size = typeof seize !== 'undefined' ? size : 25; // Default size.
    //     var gravatar_url = "http://www.gravatar.com/avatar/" +
    //                     md5( this.email.toLowerCase() )+ "?" +
    //                     'd=mm&' +
    //                     's=' + encodeURIComponent(size);
    //      return gravatar_url;
    // };




    return function(data) {
        // This is based on $injector.instantiate
        var Type = IBContactObject;
        var locals = {data:data};

        var IBContact = function() {};
        var instance;
        var returnedValue;

        // Check if Type is annotated and use just the given function at n-1 as parameter
        // e.g. someModule.factory('greeter', ['$window', function(renamed$window) {}]);
        IBContact.prototype = (angular.isArray(Type) ? Type[Type.length - 1] : Type).prototype;
        instance = new IBContact();
        returnedValue = $injector.invoke(Type, instance, locals);
        return angular.isObject(returnedValue) ? returnedValue : instance;

    };



});







