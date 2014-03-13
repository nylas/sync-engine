#!/usr/bin/env node

var zerorpc = require("zerorpc");
var client = new zerorpc.Client();

// var config = require('../config.json');
// log_in(config.username, config.password);
var API_SERVER_LOC = 'tcp://0.0.0.0:9999';

client.connect(API_SERVER_LOC);

var getSubjects = function(n) {

  client.invoke('first_n_subjects', n, function(error, response, stream) {

    console.log('\nThe first 10 emails in your inbox...\n');

    if (! response instanceof Array) {
        throw new Error('Response should be an array');
    }

    for (var i=0; i < response.length; i++) {
        var subject = response[i][0]; // first item

        console.log('    ' + subject);
    }

    process.exit();
  });
};

getSubjects(10);

