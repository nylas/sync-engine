'use strict';
var app = angular.module('InboxApp.services');


/*  Protocol handler service  */
app.factory('MockData', function ($rootScope) {
 return {

		todos : [
          {title: 'Russ: send book recommendation', complete: false},
          {title: 'Cinjon: What do you think of this article?', complete: true},
          {title: 'Alex: Can you introduce me to Sasha?', complete: true},
          {title: 'Linden: Send IFTT app feedback', complete: false},
          {title: 'Alex: Can you introduce me to Sasha?', complete: false},
          {title: 'Christine: Questions about Mission Cliffs', complete: false},
          {title: 'Charles: Debug alpha testing account', complete: false},
          {title: 'Send Mom & Dad photos from vacation', complete: false},
          {title: 'Josh: What do you think about this article?', complete: false},
          {title: 'Frank: Who\'s on first?', complete: false},
          {title: 'Sophia: Need design assets for next week', complete: false},
          {title: 'Chen-Li: Feedback for my new venture', complete: false},
          {title: 'Alex: Can you introduce me to Sasha?', complete: false},
          {title: 'Christine: Questions about Mission Cliffs', complete: false},
          {title: 'Charles: Debug alpha testing account', complete: false},
          {title: 'Send Mom & Dad photos from vacation', complete: false},
          {title: 'Josh: What do you think about this article?', complete: false},
          {title: 'Frank: Who\'s on first?', complete: false},
          {title: 'Sophia: Need design assets for next week', complete: false},
          {title: 'Chen-Li: Feedback for my new venture', complete: false},
          {title: 'Alex: Can you introduce me to Sasha?', complete: false},
          {title: 'Christine: Questions about Mission Cliffs', complete: false},
          {title: 'Charles: Debug alpha testing account', complete: false},
          {title: 'Send Mom & Dad photos from vacation', complete: false},
          {title: 'Josh: What do you think about this article?', complete: false},
          {title: 'Frank: Who\'s on first?', complete: false},
          {title: 'Sophia: Need design assets for next week', complete: false},
          {title: 'Chen-Li: Feedback for my new venture', complete: false},
          {title: 'Elizabeth: Intro to folks at PDQ Bank?', complete: false},
          {title: 'Draft: Product updates from October', complete: false}
        ],


	};
});












