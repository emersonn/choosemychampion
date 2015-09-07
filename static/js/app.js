(function() {
  var app = angular.module('league', ['ngRoute', 'ngResource', 'ngAnimate', 'ngMaterial', 'chart.js']);

  // TODO: use reverse URLs here
  app.config(['$routeProvider', function($routeProvider) {
    $routeProvider.
      when('/summoner/:playerName/:locationName', {
        controller: 'ChampionController',
        templateUrl: '/static/summoner.html'
      }).
      when('/about', {
        templateUrl: '/static/about.html'
      }).
      when('/versions', {
        templateUrl: '/static/versions.html'
      }).
      when('/', {
        templateUrl: '/static/landing.html'
      }).
      otherwise({
        redirectTo: '/'
      });
  }]);

  app.controller('ChampionController', [
      '$routeParams',
      'Champion',
      '$scope',
      'ChampionDetail',
      '$timeout',
      '$location',
  function($routeParams, Champion, $scope, ChampionDetail, $timeout, $location) {
    $scope.playerName = $routeParams.playerName;
    $scope.summoner_stats = false;

    $scope.TOP = "TOP";
    $scope.MIDDLE = "MIDDLE";
    $scope.BOTTOM = "BOTTOM";
    $scope.JUNGLE = "JUNGLE";

    $scope.getChampionData = function(champion) {
      if ($scope[champion.championId] == false || $scope[champion.championId] == undefined) {
        console.log(champion.championId + " (" + champion.role + ") requested for more data...");

        ChampionDetail.query({champion_id: champion.championId, role: champion.role}, function(data) {
          console.log("Got detailed champion data...");
          $scope[champion.championId] = true;

          $scope[champion.championId + 'Counters'] = data.counters;
          $scope[champion.championId + 'Assists'] = data.assists;

          $timeout(function() {
            $scope[champion.championId + 'Data'] = [data.days_seen.data];
            $scope[champion.championId + 'Labels'] = data.days_seen.labels;

            $scope[champion.championId + 'WonData'] = [data.days_won.data];
            $scope[champion.championId + 'WonLabels'] = data.days_won.labels;
          }, 500);
        });
      } else {
        $scope[champion.championId] = false;
      }
    }

    $scope.champions = Champion.query({username: $scope.playerName, location: $routeParams.locationName}, function(){
      console.log("Got champions...");
      $scope.summoner_stats = true;
    }, function(error) {
      console.log("Error in getting champions.");

      if (error.status == 400) {
        console.log("Summoner name does not exist.");
        $scope.summoner_stats = true;
        $scope.error_name = true;

        $timeout(function() {
          $location.path('/');
        }, 3000);
      }
    });
  }]);

  // TODO: use reverse URLs here
  app.controller('SummonerController', ['$scope', '$location', function($scope, $location) {
    $scope.locationName = "na";

    $scope.getSummoner = function() {
      if ($scope.playerName != undefined) {
        console.log("Redirecting user to summoner page...");
        $location.path("/summoner/" + $scope.playerName + "/" + $scope.locationName);
      }
    }
  }]);

  app.controller('StatsController', ['$scope', 'Numbers', function($scope, Numbers) {
    $scope.initial_stats = false;

    Numbers.get(function(data) {
      console.log("Successfully got stats.");

      $scope.initial_stats = true;
      $scope.stats = data.stats;
      $scope.winning_champ = data.winning_champ;

      $scope.picks_data = [data.champion_picks.data];
      $scope.picks_labels = data.champion_picks.labels;
      $scope.picks_images = data.champion_picks.images;

      $scope.winning_champ_data = data.winning_champ.role_distribution.data;
      $scope.winning_champ_labels = data.winning_champ.role_distribution.labels;
      $scope.winning_champ_assists = data.winning_champ.assists;
    });
  }]);

  app.directive("filteredChamps", function() {
    return {
      restrict: "E",
      templateUrl: "/static/championList.html",
      scope: {
        certainFilter: '='
      }
    };
  });

  app.factory('Champion', ['$resource', function($resource) {
    return $resource('/api/champions/:username/:location',
      {username: '@username', location: '@location'},
      {query: {method: 'GET', params: {username: '@username', location: '@location'}}});
  }]);

  app.factory('ChampionDetail', ['$resource', function($resource) {
    return $resource('/api/stats/:champion_id/:role',
      {champion_id: '@champion_id', role: '@role'},
      {query: {method: 'GET', params: {champion_id: '@champion_id', role: '@role'}}});
  }]);

  app.factory('Numbers', ['$resource', function($resource) {
    console.log("Getting stats...");
    return $resource('/api/numbers/');
  }]);

  app.filter('unsafe', ['$sce', function($sce) {
    return function(text) {
      return $sce.trustAsHtml(text);
    }
  }]);

  $("#summonerName").focus();
})();
