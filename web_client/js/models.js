
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

app.factory('IBMessage', function ($injector, md5) {

    function IBMessageObject($rootScope, data) {
        this.$rootScope = $rootScope;

        // Propogate fields to the object
        for (var key in data) {
            if (self.hasOwnProperty(key)) {
                console.log(key + " -> " + data[key]);
            }
            this[key] = data[key];
        }
        // Fix the date
        this.date = new Date(data.date.$date);

        var gravatar_size = 25;
        this.gravatar_url = "https://www.gravatar.com/avatar/" +
                        md5.createHash( this.from[1].toLowerCase() )+ "?" +
                        'd=mm&' +
                        's=' + encodeURIComponent(gravatar_size);

        if (this.to && this.to.length > 0) {

            var to_list = [];
            for (var i = 0; i < this.to.length; i++) {
                var c = this.to[i];
                var nameToShow;
                if (c[0]) {
                    nameToShow = c[0];
                } else {
                    nameToShow = c[1];
                }
                to_list.push(nameToShow);
            }
            this.contactDisplayList = to_list.join(', ');
        } else {
            this.contactDisplayList = 'Unknown sender';
        }

        this.attachments = [];
    }

    IBMessageObject.prototype.fromName = function() {
        return this.from[0];
    };

    IBMessageObject.prototype.fromEmail = function() {
        return this.from[1];
    };

    IBMessageObject.prototype.printDate = function() {
        // var curr_date = this.date.getDate();
        // var curr_month = this.date.getMonth() + 1; //Months are zero based
        // var curr_year = this.date.getFullYear();
        // return curr_date + "-" + curr_month + "-" + curr_year;

        return this.date.toLocaleString();
    };

    return function(data) {
        // This is based on $injector.instantiate
        var Type = IBMessageObject;
        var locals = {data:data};

        var IBMessage = function() {};
        var instance;
        var returnedValue;

        // Check if Type is annotated and use just the given function at n-1 as
        // parameter
        // e.g. someModule.factory('greeter', ['$window',
        // function(renamed$window) {}]);
        IBMessage.prototype = (angular.isArray(Type) ? Type[Type.length - 1]
                                                     : Type).prototype;
        instance = new IBMessage();
        returnedValue = $injector.invoke(Type, instance, locals);
        return angular.isObject(returnedValue) ? returnedValue : instance;
    };
});

app.factory('IBThread', function ($injector, md5, IBMessage) {

    function IBThreadObject($rootScope, data) {
        this.$rootScope = $rootScope;

        function sortByDate(msg1, msg2) {
            var a = msg1.date.getTime();
            var b = msg2.date.getTime();
            if (a > b) return 1;
            if (a < b) return -1;
            return 0;
        }

        var thread = this;
        angular.forEach(data, function(value, key) {
            if (key === 'messages') {
                thread.messages = [];
                angular.forEach(value, function(msg, i) {
                    thread.messages.push(new IBMessage(msg));
                });
                thread.messages.sort(sortByDate);
            }
            else {
                if (thread.hasOwnProperty(key)) {
                    console.log(key + " -> " + value);
                }
                thread[key] = value;
            }
        });
    }

    IBThreadObject.prototype.recentMessage = function() {
        return this.messages[this.messages.length - 1];
    };

    IBThreadObject.prototype.snippet = function() {
        return this.messages[0].snippet;
    };

    return function(data) {
        // This is based on $injector.instantiate
        var Type = IBThreadObject;
        // var locals = {messages:messages};
        var locals = {data:data};

        var IBThread = function() {};
        var instance;
        var returnedValue;

        // Check if Type is annotated and use just the given function at n-1 as
        // parameter
        // e.g. someModule.factory('greeter', ['$window',
        // function(renamed$window) {}]);
        IBThread.prototype = (angular.isArray(Type) ? Type[Type.length - 1]
                                                    : Type).prototype;
        instance = new IBThread();

        returnedValue = $injector.invoke(Type, instance, locals);
        return angular.isObject(returnedValue) ? returnedValue : instance;
    };
});

app.factory('IBTodo', function ($injector)
{
    function IBTodoObject($rootScope, data) {
        this.$rootScope = $rootScope;

        // Propogate fields to the object
        for (var key in data) {
            if (self.hasOwnProperty(key)) {
                console.log(key + " -> " + p[key]);
            }
            this[key] = data[key];
        }
    }

    IBTodoObject.prototype.fromName = function() {
        return this.from[0];
    };

    IBTodoObject.prototype.fromEmail = function() {
        return this.from[1];
    };

    IBTodoObject.prototype.printDate = function() {
        // var curr_date = this.date.getDate();
        // var curr_month = this.date.getMonth() + 1; //Months are zero based
        // var curr_year = this.date.getFullYear();
        // return curr_date + "-" + curr_month + "-" + curr_year;

        return this.date.toLocaleString();
    };

    return function(data) {
        // This is based on $injector.instantiate
        var Type = IBTodoObject;
        var locals = {data:data};
        var IBTodo = function() {};
        var instance;
        var returnedValue;
        // Check if Type is annotated and use just the given function at n-1 as parameter
        // e.g. someModule.factory('greeter', ['$window', function(renamed$window) {}]);
        IBTodo.prototype = (angular.isArray(Type) ? Type[Type.length - 1] : Type).prototype;
        instance = new IBTodo();

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
