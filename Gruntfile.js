"use strict";

module.exports = function (grunt) {

  require("time-grunt")(grunt);

  grunt.initConfig({
    pkg: grunt.file.readJSON("package.json"),

    yeoman: {
      app:  "web_client",
      dist: "web_client/dist"
    },

    // Make sure code styles are up to par and there are no obvious mistakes
    jshint: {
      options: {
        jshintrc: ".jshintrc",
        reporter: require("jshint-stylish")
      },
      all: [
        "Gruntfile.js",
        "<%= yeoman.app %>/js/{,*/}*.js"
      ],
    },

    // Empties folders to start fresh
    clean: {
      dist: {
        files: [{
          dot: true,
          src: [
            ".tmp",
            "<%= yeoman.dist %>/*",
            "!<%= yeoman.dist %>/.git*"
          ]
        }]
      },
    },

    ngmin: {
      build: {
        src: ["<%= yeoman.app %>/js/**/*.js"],
        dest: "<%= yeoman.dist %>/<%= pkg.name %>.combined.js",
      }
    },


    ngtemplates: {
      InboxApp: {
        src: "<%= yeoman.app %>/views/**.html",
        dest: "<%= yeoman.dist %>/templates.js",
        options: {
          htmlmin: {
            collapseWhitespace: true,
            collapseBooleanAttributes: true
          }
        }
      }
    },

    uglify: {
      options: {
        banner: "/*! <%= pkg.name %> <%= grunt.template.today('dd-mm-yyyy') %> */\n",
        mangle: false,
      },
      dist: {
        files: {
          "<%= yeoman.dist %>/<%= pkg.name %>.compressed.js": [
            "<%= yeoman.dist %>/<%= pkg.name %>.combined.js"
          ]
        }
      }
    },

  });

  grunt.loadNpmTasks("grunt-contrib-uglify");
  grunt.loadNpmTasks("grunt-contrib-jshint");
  grunt.loadNpmTasks("grunt-contrib-qunit");
  grunt.loadNpmTasks("grunt-contrib-concat");
  grunt.loadNpmTasks("grunt-ngmin");
  grunt.loadNpmTasks("grunt-angular-templates");

  grunt.registerTask("default", ["jshint", "ngmin", "ngtemplates",
    "uglify"
  ]);

};