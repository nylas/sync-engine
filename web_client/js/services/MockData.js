'use strict';
var app = angular.module('InboxApp.services');


/*  Protocol handler service  */
app.factory('MockData', function ($rootScope) {
 return {

		todos : [
          {display_name: 'Russ: send book recommendation', completed: false},
          {display_name: 'Cinjon: What do you think of this article?', completed: true},
          {display_name: 'Alex: Can you introduce me to Sasha?', completed: true},
          {display_name: 'Linden: Send IFTT app feedback', completed: false},
          {display_name: 'Alex: Can you introduce me to Sasha?', completed: false},
          {display_name: 'Christine: Questions about Mission Cliffs', completed: false},
          {display_name: 'Charles: Debug alpha testing account', completed: false},
          {display_name: 'Send Mom & Dad photos from vacation', completed: false},
          {display_name: 'Josh: What do you think about this article?', completed: false},
          {display_name: 'Frank: Who\'s on first?', completed: false},
          {display_name: 'Sophia: Need design assets for next week', completed: false},
          {display_name: 'Chen-Li: Feedback for my new venture', completed: false},
          {display_name: 'Alex: Can you introduce me to Sasha?', completed: false},
          {display_name: 'Christine: Questions about Mission Cliffs', completed: false},
          {display_name: 'Charles: Debug alpha testing account', completed: false},
          {display_name: 'Send Mom & Dad photos from vacation', completed: false},
          {display_name: 'Josh: What do you think about this article?', completed: false},
          {display_name: 'Frank: Who\'s on first?', completed: false},
          {display_name: 'Sophia: Need design assets for next week', completed: false},
          {display_name: 'Chen-Li: Feedback for my new venture', completed: false},
          {display_name: 'Alex: Can you introduce me to Sasha?', completed: false},
          {display_name: 'Christine: Questions about Mission Cliffs', completed: false},
          {display_name: 'Charles: Debug alpha testing account', completed: false},
          {display_name: 'Send Mom & Dad photos from vacation', completed: false},
          {display_name: 'Josh: What do you think about this article?', completed: false},
          {display_name: 'Frank: Who\'s on first?', completed: false},
          {display_name: 'Sophia: Need design assets for next week', completed: false},
          {display_name: 'Chen-Li: Feedback for my new venture', completed: false},
          {display_name: 'Elizabeth: Intro to folks at PDQ Bank?', completed: false},
          {display_name: 'Draft: Product updates from October', completed: false}
        ],


	};
});












