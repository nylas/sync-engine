"use strict";

module.exports = function (grunt) {

  // Time how long tasks take.
  require("time-grunt")(grunt);

  grunt.initConfig({
    pkg: grunt.file.readJSON("package.json"),

    // Make sure code styles are up to par and there are no obvious mistakes
    jshint: {
      options: {
        jshintrc: ".jshintrc",
        reporter: require("jshint-stylish")
      },
      all: [
        "Gruntfile.js",
        "web_client/js/{,*/}*.js"
      ],
      // test: {
      //   options: {
      //     jshintrc: "test/.jshintrc"
      //   },
      //   src: ["test/spec/{,*/}*.js"]
      // }
    },



    ngmin: {
      build: {
        src: ["web_client/js/**/*.js"],
        dest: "web_client/build/<%= pkg.name %>.combined.js",
      }
    },


    ngtemplates: {
      InboxApp: {
        src: "web_client/views/**.html",
        dest: "web_client/build/templates.js",
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
          "web_client/build/<%= pkg.name %>.compressed.js": [
            "web_client/build/<%= pkg.name %>.combined.js"
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