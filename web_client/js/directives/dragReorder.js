/*
  A LOT of this code comes from the angular.js project

  additionally this uses zest for dom selection and hammer.js (with an angular-hammer wrapper) for touch and mouse-drag event support
*/

'use strict';
var app = angular.module('InboxApp.directives');

// Stupid fucking linting warnings
var console = console;
var angular = angular;

app.directive('cuReorderHandle', function() {
  return {
    transclude: false,
    priority: 999,
    terminal: false,
    compile: function(element, attr, linker) {
      var dragElement;
      dragElement = angular.element(zest(attr.cuReorderHandle, element[0])[0]);
      if (dragElement != null) {
        dragElement.attr("hm-drag", "reorderFuncs.moveevent($event, $elementRef, $index)");
        dragElement.attr("hm-dragstart", "reorderFuncs.startevent($event, $elementRef, $index)");
        return dragElement.attr("hm-dragend", "reorderFuncs.stopevent($event, $elementRef, $index)");
      }
    }
  };
});

app.directive('cuRepeatReorder', function() {
  return {
    transclude: "element",
    priority: 1000,
    terminal: true,
    compile: function(element, attr, linker) {
      return function(scope, iterStartElement, attr) {
        var expression, keyIdent, lastOrder, lhs, match, ngRepeatWatch, reorderFuncs, rhs, valueIdent;
        expression = attr.cuRepeatReorder;
        match = expression.match(/^\s*(.+)\s+in\s+(.*)\s*$/);
        lhs = void 0;
        rhs = void 0;
        valueIdent = void 0;
        keyIdent = void 0;
        if (!match) {
          throw Error("Expected ngRepeat in form of '_item_ in _collection_' but got '" + expression + "'.");
        }
        lhs = match[1];
        rhs = match[2];
        match = lhs.match(/^(?:([\$\w]+)|\(([\$\w]+)\s*,\s*([\$\w]+)\))$/);
        if (!match) {
          throw Error("'item' in 'item in collection' should be identifier or (key, value) but got '" + lhs + "'.");
        }
        valueIdent = match[3] || match[1];
        keyIdent = match[2];

        reorderFuncs = {
          offset: 0,
          gesture: 'vertical',
          setMargins: function($element, top, bottom) {
            if (top == null) {
              top = "";
            }
            if (bottom == null) {
              bottom = "";
            }
            $element.css("margin-top", top);
            $element.css("margin-bottom", bottom);
            return $element.css("border-top", "");
          },

          resetMargins: function() {
            var c, _i, _len, _ref, _results;
            _ref = scope.$eval(rhs);
            _results = [];
            for (_i = 0, _len = _ref.length; _i < _len; _i++) {
              c = _ref[_i];
              _results.push(this.setMargins(lastOrder.peek(c).element));
            }
            return _results;
          },

          updateElementClass: function($element) {
            if (this.gesture === "vertical") {
              return $element.addClass('dragging');
            } else {
              return $element.removeClass('dragging');
            }
          },

          updateOffset: function($event, $element, $index) {
            var afterIndex, beforeIndex, bottomMargin, collection, count, delta, directedHeight, gDirection, halfHeight, topMargin, workingDelta, workingElement, _ref, _ref1, _ref2;
            this.offset = 0;
            collection = scope.$eval(rhs);
            workingDelta = $event.gesture.deltaY;
            gDirection = $event.gesture.deltaY < 0 ? "up" : "down";
            directedHeight = $element[0].offsetHeight * (gDirection === "up" ? -1 : 1);
            workingElement = $element[0];
            halfHeight = 0;
            workingDelta += directedHeight / 2;
            while ((gDirection === "down" && workingDelta > 0 && $index + this.offset < collection.length) || (gDirection === "up" && workingDelta < 0 && $index + this.offset >= 0)) {
              if (gDirection === "down") {
                this.offset++;
              } else {
                this.offset--;
              }
              if (gDirection === "down" && $index + this.offset >= collection.length) {
                workingElement = lastOrder.peek(collection[$index + this.offset - 1]).element;
                break;
              }
              if (gDirection === "up" && $index + this.offset < 0) {
                workingElement = lastOrder.peek(collection[0]).element;
                break;
              }
              workingElement = lastOrder.peek(collection[$index + this.offset]).element;
              this.setMargins(workingElement);
              if ((collection.length > (_ref = $index - this.offset) && _ref >= 0) && this.offset !== 0) {
                this.setMargins(lastOrder.peek(collection[$index - this.offset]).element);
              }
              workingDelta += workingElement[0].offsetHeight * (gDirection === "down" ? -1 : 1);
            }
            if (!((-1 <= (_ref1 = this.offset) && _ref1 <= 1))) {
              bottomMargin = "" + (workingElement.css("margin-bottom").replace(/^[0-9\.]/g, '') + $element[0].offsetHeight) + "px";
              topMargin = "" + (workingElement.css("margin-top").replace(/^[0-9\.]/g, '') + $element[0].offsetHeight) + "px";
              if (gDirection === "up") {
                if ($index + this.offset < 0) {
                  this.setMargins(workingElement, topMargin);
                } else {
                  this.setMargins(workingElement, "", bottomMargin);
                }
              }
              if (gDirection === "down") {
                if ($index + this.offset >= collection.length) {
                  this.setMargins(workingElement, "", bottomMargin);
                } else {
                  this.setMargins(workingElement, topMargin);
                }
              }
            }
            count = 1 + ($index + this.offset < 0 || $index + this.offset >= collection.length ? 2 : 0);
            while ($index + this.offset + count < collection.length || $index + this.offset - count >= 0) {
              if ($index + this.offset + count < collection.length) {
                this.setMargins(lastOrder.peek(collection[$index + this.offset + count]).element);
              }
              if ($index + this.offset - count >= 0) {
                this.setMargins(lastOrder.peek(collection[$index + this.offset - count]).element);
              }
              count++;
            }
            workingDelta -= directedHeight / 2;
            if ((workingDelta <= 0 && gDirection === "down") || (workingDelta >= 0 && gDirection === "up")) {
              delta = $event.gesture.deltaY;
            } else {
              delta = $event.gesture.deltaY - workingDelta;
            }
            if ((-1 <= (_ref2 = this.offset) && _ref2 <= 1)) {
              this.setMargins($element, "" + delta + "px", "" + (-delta) + "px");
              beforeIndex = $index - 1;
              afterIndex = $index + 1;
            } else if (this.offset < 0) {
              if ($index > 1) {
                this.setMargins(lastOrder.peek(collection[$index - 1]).element);
              }
              this.setMargins($element, "" + (delta - $element[0].offsetHeight) + "px", "" + (-(delta + (0.5 * $element[0].offsetHeight))) + "px");
              beforeIndex = $index + this.offset;
              afterIndex = $index + this.offset + 1;
            } else {
              if ($index < collection.length - 2) {
                this.setMargins(lastOrder.peek(collection[$index + 1]).element);
              }
              this.setMargins($element, "" + (delta - (0 * $element[0].offsetHeight)) + "px", "" + (-(delta + $element[0].offsetHeight)) + "px");
              beforeIndex = $index + this.offset - 1;
              afterIndex = $index + this.offset;
            }
            angular.element(zest(".dragging-before")).removeClass("dragging-before");
            angular.element(zest(".dragging-after")).removeClass("dragging-after");
            if (beforeIndex >= 0) {
              lastOrder.peek(collection[beforeIndex]).element.addClass("dragging-before");
            }
            if (afterIndex < collection.length) {
              return lastOrder.peek(collection[afterIndex]).element.addClass("dragging-after");
            }
          },

          moveevent: function($event, $element, $index) {
            this.updateElementClass($element);
            if (this.gesture === "vertical") {
              this.updateOffset($event, $element, $index);
              $event.preventDefault();
              $event.stopPropagation();
              $event.gesture.stopPropagation();
              return false;
            } else {
              return this.resetMargins();
            }
          },

          startevent: function($event, $element, $index) {
            $element.parent().addClass("active-drag-below");
            this.gesture = $event.gesture.direction === "up" || $event.gesture.direction === "down" ? "vertical" : "horizontal";
            this.updateElementClass($element);
            this.offset = 0;
            this.updateOffset($event, $element);
            return $event.preventDefault();
          },

          stopevent: function($event, $element, $index) {
            var collection, obj;
            $element.parent().removeClass("active-drag-below");
            this.resetMargins();
            angular.element(zest(".dragging-before")).removeClass("dragging-before");
            angular.element(zest(".dragging-after")).removeClass("dragging-after");
            if (this.offset !== 0) {
              collection = scope.$eval(rhs);
              obj = collection.splice($index, 1);
              if (this.offset < 0) {
                collection.splice($index + this.offset + 1, 0, obj[0]);
              } else if (this.offset > 0) {
                collection.splice($index + this.offset - 1, 0, obj[0]);
              }
            }
            $element.removeClass('dragging');
            return $event.preventDefault();
          }
        };

        lastOrder = new HashQueueMap();

        return scope.$watch(ngRepeatWatch = function(scope) {
          var array, arrayBound, childScope, collection, cursor, index, key, last, length, nextOrder, value;
          index = void 0;
          length = void 0;
          collection = scope.$eval(rhs);
          cursor = iterStartElement;
          nextOrder = new HashQueueMap();
          arrayBound = void 0;
          childScope = void 0;
          key = void 0;
          value = void 0;
          array = void 0;
          last = void 0;
          if (!isArray(collection)) {
            array = [];
            for (key in collection) {
              if (collection.hasOwnProperty(key) && key.charAt(0) !== "$") {
                array.push(key);
              }
            }
            array.sort();
          } else {
            array = collection || [];
          }
          arrayBound = array.length - 1;
          index = 0;
          length = array.length;
          while (index < length) {
            key = (collection === array ? index : array[index]);
            value = collection[key];
            last = lastOrder.shift(value);
            if (last) {
              childScope = last.scope;
              nextOrder.push(value, last);
              if (index === last.index) {
                cursor = last.element;
              } else {
                last.index = index;
                cursor.after(last.element);
                cursor = last.element;
              }
            } else {
              childScope = scope.$new();
            }
            childScope[valueIdent] = value;
            if (keyIdent) {
              childScope[keyIdent] = key;
            }
            childScope.$index = index;
            childScope.$first = index === 0;
            childScope.$last = index === arrayBound;
            childScope.$middle = !(childScope.$first || childScope.$last);
            childScope.reorderFuncs = reorderFuncs;
            if (!last) {
              linker(childScope, function(clone) {
                cursor.after(clone);
                last = {
                  scope: childScope,
                  element: (cursor = clone),
                  index: index
                };
                childScope.$elementRef = last.element;
                return nextOrder.push(value, last);
              });
            }
            index++;
          }
          for (key in lastOrder) {
            if (lastOrder.hasOwnProperty(key)) {
              array = lastOrder[key];
              while (array.length) {
                value = array.pop();
                value.element.remove();
                value.scope.$destroy();
              }
            }
          }
          lastOrder = nextOrder;
        });
      };
    }
  };
});
