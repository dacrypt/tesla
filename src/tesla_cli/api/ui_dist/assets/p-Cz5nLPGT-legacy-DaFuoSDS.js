System.register(["./index-legacy-Dw1A-KqS.js"],function(t,e){"use strict";var n,r,i;return{setters:[t=>{n=t.z,r=t.A,i=t.B}],execute:function(){
/*!
			 * (C) Ionic http://ionicframework.com - MIT License
			 */
t("createSwipeBackGesture",(t,e,s,o,c)=>{const a=t.ownerDocument.defaultView;let u=n(t);const l=t=>u?-t.deltaX:t.deltaX;return r({el:t,gestureName:"goback-swipe",gesturePriority:101,threshold:10,canStart:r=>(u=n(t),(t=>{const{startX:e}=t;return u?e>=a.innerWidth-50:e<=50})(r)&&e()),onStart:s,onMove:t=>{const e=l(t);o(e/a.innerWidth)},onEnd:t=>{const e=l(t),n=a.innerWidth,r=e/n,s=(h=t,u?-h.velocityX:h.velocityX),o=s>=0&&(s>.2||e>n/2),d=(o?1-r:r)*n;var h;let g=0;if(d>5){const t=d/Math.abs(s);g=Math.min(t,540)}c(o,r<=0?.01:i(0,r,.9999),g)}})})}}});
