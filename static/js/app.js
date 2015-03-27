    (function() {
      var app = angular.module('league', ['ngMaterial', 'ngRoute', 'ngResource', 'ngAnimate']);

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

        $mdThemingProvider.theme('default')
          .primaryPalette('cyan')
          .accentPalette('amber');
      }]);

      app.controller("SummonerController", ['$http', '$location', function($http, $location) {
        this.playerName = "";

        this.getSummoner = function() {
          console.log("Getting summoner " + this.playerName);
          $location.path('/summoner/' + this.playerName);
        }
      }]);

      app.controller("ChampionsController", ['$http', '$location', '$routeParams', 'SessionService', 'Champion', '$scope',
        function($http, $location, $routeParams, SessionService, Champion, $scope) {
          $scope.playerName = "";
          $scope.playerName = $routeParams.summonerName;
          $scope.playerId = 0;
          $scope.champions = {};

          $scope.data = {
            selectedIndex: 0,
          };

          $scope.TOP = "TOP";
          $scope.MIDDLE = "MIDDLE";
          $scope.BOTTOM = "BOTTOM";
          $scope.JUNGLE = "JUNGLE";

          $scope.gettingData = true;
          $scope.gotError = false;

          $scope.next = function() {
            $scope.data.selectedIndex = Math.min($scope.data.selectedIndex + 1, 3);
          };

          $scope.previous = function() {
            $scope.data.selectedIndex = Math.max($scope.data.selectedIndex - 1, 0);
          };

          $scope.backToFront = function() {
            $location.path("/");
          };

          SessionService.StartSession($scope.playerName).then(function(data) {
            console.log("Yay! Found player " + data['data']['user_id'] + " from " + $scope.summonerName + ".");
            $scope.playerId = data['data']['user_id'];

            // need to add handler for this for retries
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

      app.factory('Champion', ['$resource', function($resource) {
        // return $resource('/api/stats/:username/:user_id', {}, {
        //   query: {method: 'GET', isArray: true}
        // });
        return $resource('/api/stats/:username/:userId',
          {username: '@username', userId: '@userId'},
          {query: {method: 'GET', params: {username: '@username', userId: '@userId'}}});
      }]);

      app.directive('summonerLogin', function() {
        return {
          restrict: 'E',
          templateUrl: 'main.html'
        }
      });

      app.directive("filteredChamps", function() {
        return {
          restrict: "E",
          templateUrl: "/static/championList.html",
          scope: {
            certainFilter: '='
          }
        };
      });

      app.filter('encodeURIComponent', function() {
        return window.encodeURIComponent;
      });
    })();
