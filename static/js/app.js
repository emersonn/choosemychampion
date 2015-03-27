    (function() {
      // todo: clean this up

      // defines the app, takes the Material, Route, Resource, and Animate dependencies
      var app = angular.module('league', ['ngMaterial', 'ngRoute', 'ngResource', 'ngAnimate']);

      // configures the app, mostly used to configure routes
      // routes are used to keep the user in the same page without reloads
      app.config(['$routeProvider', '$httpProvider', '$mdThemingProvider', function($routeProvider, $httpProvider, $mdThemingProvider) {
        $routeProvider.when('/', {
          controller: 'SummonerController',
          templateUrl: '/static/main.html'
        }).when('/summoner/:summonerName', {
          controller: 'ChampionsController',
          templateUrl: '/static/champions.html'
        }).otherwise({
          redirectTo: '/'
        });

        // defines the color palette for the material themes
        $mdThemingProvider.theme('default')
          .primaryPalette('cyan')
          .accentPalette('amber');
      }]);

      // main page controller. sets the playername and when the player name is received it
      // redirects the user to the respective summoner
      app.controller("SummonerController", ['$http', '$location', function($http, $location) {
        this.playerName = "";

        this.getSummoner = function() {
          console.log("Getting summoner " + this.playerName);
          $location.path('/summoner/' + this.playerName);
        }
      }]);

      // the champions controller. requests the champion data from the server
      // and routes it to the template for display
      app.controller("ChampionsController", ['$http', '$location', '$routeParams', 'SessionService', 'Champion', '$scope',
        function($http, $location, $routeParams, SessionService, Champion, $scope) {
          $scope.playerName = "";
          $scope.playerName = $routeParams.summonerName;

          $scope.playerId = 0;

          // storage for all the data
          $scope.champions = {};

          // used for the tabs
          $scope.data = {
            selectedIndex: 0,
          };

          $scope.TOP = "TOP";
          $scope.MIDDLE = "MIDDLE";
          $scope.BOTTOM = "BOTTOM";
          $scope.JUNGLE = "JUNGLE";

          // used for template display of particular data messages
          $scope.gettingData = true;
          $scope.gotError = false;

          // tab functions
          $scope.next = function() {
            $scope.data.selectedIndex = Math.min($scope.data.selectedIndex + 1, 3);
          };

          $scope.previous = function() {
            $scope.data.selectedIndex = Math.max($scope.data.selectedIndex - 1, 0);
          };

          $scope.backToFront = function() {
            $location.path("/");
          };

          // requests data from the server and stores it in the controller
          SessionService.StartSession($scope.playerName).then(function(data) {
            console.log("Yay! Found player " + data['data']['user_id'] + " from " + $scope.summonerName + ".");
            $scope.playerId = encodeURI(data['data']['user_id']);

            // todo: add handler for retries of the full information and also
            // giving better error feedback
            console.log("Now requesting full information...");
            $scope.champions = Champion.query({username: $scope.playerName, userId: $scope.playerId}, function(){
              console.log("Finished the query...");
              $scope.gettingData = false;
            }, function() {
              $scope.gotError = true;
            });
          }).catch(function() {
            console.log("Oh no!");
            $scope.gotError = true;
          });
      }]);

      // starts the session for attempting to query player name data
      app.service('SessionService', ['$http', '$q', '$timeout', function($http, $q, $timeout) {
        var _this = this;
        var _maxRetryCount = 5;

        this.StartSession = function(username, retries) {
          retries = angular.isUndefined(retries) ? _maxRetryCount : retries;

          return $http.get('/api/' + username)
            .then(function(data) {
              return data;
            }, function(error) {
              if (retries > 0) {
                console.log("Trying again with " + retries + ".");
                var defer = $q.defer();

                $timeout(function() {
                  defer.resolve(_this.StartSession(username, --retries))
                }, 2500);
                return defer.promise;
              }
              return $q.reject('oops!');
            });
        }
      }]);

      // todo: implementing more responsive data collection. if it doesn't connect
      // it doesn't give good error information or even retries.

      // the storage unit for storing champion data. calling .query() returns all
      // of the data to use.
      app.factory('Champion', ['$resource', function($resource) {
        // return $resource('/api/stats/:username/:user_id', {}, {
        //   query: {method: 'GET', isArray: true}
        // });
        return $resource('/api/stats/:username/:userId',
          {username: '@username', userId: '@userId'},
          {query: {method: 'GET', params: {username: '@username', userId: '@userId'}}});
      }]);

      // handles the view for the index
      app.directive('summonerLogin', function() {
        return {
          restrict: 'E',
          templateUrl: 'main.html'
        }
      });

      // handles the view for the champion listings, and allow for refactoring
      // of the champion list
      app.directive("filteredChamps", function() {
        return {
          restrict: "E",
          templateUrl: "/static/championList.html",
          scope: {
            certainFilter: '='
          }
        };
      });

      // filter for encoding URIs
      app.filter('encodeURIComponent', function() {
        return window.encodeURIComponent;
      });
    })();
