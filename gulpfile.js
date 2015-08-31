var gulp = require('gulp');

var uglify = require('gulp-uglify');
var rename = require('gulp-rename');
var concat = require('gulp-concat');
var minifyCss = require('gulp-minify-css');

// Concatenate and Compress CSS
gulp.task('minify-css', function() {
  return gulp.src([
    'static/css/skeleton.css',
    'static/css/hover-min.css',
    'static/css/animate.css',
    'static/css/app.css'
  ])
  .pipe(concat('all.css'))
  .pipe(gulp.dest('static/dist'))
  .pipe(rename('all.min.css'))
  .pipe(minifyCss())
  .pipe(gulp.dest('static/dist'))
});

// Concatenate and Minify JS
gulp.task('scripts', function() {
  return gulp.src([
    'static/js/Chart.js',
    'static/js/angular-chart.min.js',
    'static/js/app.js'
  ])
    .pipe(concat('all.js'))
    .pipe(gulp.dest('static/dist'))
    .pipe(rename('all.min.js'))
    .pipe(uglify())
    .pipe(gulp.dest('static/dist'));
});

gulp.task('watch', function() {
  gulp.watch('static/js/*.js', ['scripts']);
  gulp.watch('static/css/*.css', ['minify-css']);
  // gulp.watch('static/css/*.css', )
});

gulp.task('default', ['minify-css', 'scripts', 'watch']);
