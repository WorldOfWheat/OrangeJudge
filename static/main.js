var main = $("#main_area");
var $body = (window.opera) ? (document.compatMode == "CSS1Compat" ? $('html') : $('body')) : $('html,body');
//code copy
var copyer = document.createElement("textarea");
document.body.appendChild(copyer);
$(copyer).hide();
$("div.highlight").addClass("codehilite");
$("div.highlight").removeClass("highlight");
$("div.codehilite").each(function() {
    let text = $(this).text();
    let p = $(this);
    let copy = $('<button class="copy_btn">copy</button>');
    p.append(copy);
    p.css("position","relative");
    copy.click(function() {
        copyer.value = text;
        copyer.select();
        copyer.setSelectionRange(0, 99999);
        navigator.clipboard.writeText(copyer.value);
    });
});
$("pdf-file").each(function(){
    $(this).append('<embed src="'+$(this).attr("src")+'" type="application/pdf" width="100%" height="100%">')
});
$("textarea").each(function(){
    $(this).data("default-rows",$(this).attr("rows"));
});
$("textarea").on("input",function(){
    $(this).css("height",$(this).prop("scrollHeight")+"px");
});
window.setTimeout(function(){
    $("textarea").each(function(){
        $(this).css("height",$(this).prop("scrollHeight")+"px");
    });
},1000);
$("textarea").on('keydown', function(e) {
  if (e.key == 'Tab') {
    e.preventDefault();
    var start = this.selectionStart;
    var end = this.selectionEnd;

    // set textarea value to: text before caret + tab + text after caret
    this.value = this.value.substring(0, start) +
      "    " + this.value.substring(end);

    // put caret at right position again
    this.selectionStart =
      this.selectionEnd = start + 1;
  }
});
function timestamp_to_str(i){
    return new Date(+i*1000).toLocaleString()
}
$(".date-string").each(function(){
    $(this).text(timestamp_to_str($(this).text()));
});
$("input[type='datetime-local'][data-value]").each(function(){
    let $this = $(this);
    let s = new Date(+$this.data("value")*1000 - (new Date()).getTimezoneOffset() * 60000).toISOString();
    $this.val(s.substr(0,s.length-1));
});
$("input[type='datetime-local']").each(function(){
    let $this = $(this);
    let nw = $("<input>").attr("type","hidden").attr("name",$this.attr("name")).val(new Date($this.val()).getTime()/1000);
    $this.after(nw);
    $this.removeAttr("name");
    $this.on("input",function(){
        nw.val(new Date($this.val()).getTime()/1000);
    });
});
$(".countdown-timer").each(function(){
    let $this = $(this);
    let target = +$this.data("target")*1000;
    let is_zero = target - (new Date()).getTime()<=0;
    window.setInterval(function(){
        let delta = Math.max(0,target - (new Date()).getTime());
        delta = Math.floor(delta/1000);
        let sec = ""+(delta%60);
        let min = ""+(Math.floor(delta/60)%60);
        let hr = ""+Math.floor(delta/3600);
        if(sec.length<2) sec = "0"+sec;
        if(min.length<2) min = "0"+min;
        $this.text(hr+":"+min+":"+sec);
        if (!is_zero && (delta<=0)) location.reload();
    },100);
});
$("select[data-value]").each(function(){
    let val = $(this).data("value");
    $(this).val(val).change();
});
$(".time-string").each(function(){
    let t = Math.floor(+$(this).text());
    let d = Math.floor(t/1440);
    let h = Math.floor((t%1440)/60);
    let m = t%60;
    $(this).text((d>0?d+':':'')+(h<10?"0":"")+h+":"+(m<10?"0":"")+m);
});
var myModal = bootstrap.Modal.getOrCreateInstance(document.getElementById('myModal'));
function show_modal(title, text, refresh, next_page){
    document.getElementById('myModal').focus();
    $("#myModalTitle").text(title);
    $("#myModalText").text(text);
    if (next_page) {
        console.log("branch 1");
        $("#myModal").on("hidden.bs.modal", function(){
            location.href = next_page;
        });
    }else if (refresh) {
        console.log("branch 2");
        $("#myModal").on("hidden.bs.modal", function(){
            location.reload();
        });
    }
    myModal.show();
}
$("input[data-checked]").each(function(){
    $(this).prop("checked",$(this).data("checked")==="True")
});
$("div.radio-selector[data-value]").each(function(){
    let val = $(this).data("value");
    $(this).find("input[value="+val+"]").prop("checked",true);
});
$("*[data-disabled]").each(function(){
    if($(this).data("disabled")==="True"){
        $(this).prop("disabled",true);
        $(this).addClass("disabled");
    }
});
$("*[data-active]").each(function(){
    if($(this).data("active")==="True"){
        $(this).addClass("active");
    }
});
$("a[data-args]").each(function(){
    let o = $(this).data("args").split("=");
    let url = new URL(location.href);
    if (url.searchParams.has(o[0])){
        url.searchParams.set(o[0],o[1]);
    }else{
        url.searchParams.append(o[0],o[1]);
    }
    $(this).attr("href",url.href);
});
let url = new URL(location.href);
url.pathname = "/login"
url.searchParams.append("next",location.pathname);
if (location.pathname=="/login"){
    $("#login_btn").hide();
}else{
    $("#login_btn").attr("href",url.href)
}
function _uuid() {
  var d = Date.now();
  if (typeof performance !== 'undefined' && typeof performance.now === 'function'){
    d += performance.now(); //use high-precision timer if available
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    var r = (d + Math.random() * 16) % 16 | 0;
    d = Math.floor(d / 16);
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}
$("form").each(function(){
    $(this).append($("#csrf_token").clone().removeAttr("id"));
});
function fetching(form){
    return fetch(form.attr("action"),{
        method: form.attr("method"),
        headers: {"x-csrf-token": $("#csrf_token").val()},
        body: new FormData(form[0])
    });
}
function post(url, data, callback){
    $.ajax({
        url: url,
        method: "POST",
        contentType: "application/x-www-form-urlencoded",
        headers: {"x-csrf-token": $("#csrf_token").val()},
        data: data,
        error: function(xhr, status, content){
            callback(content, status, xhr)
        },
        success: function(content, status, xhr){
            callback(content, status, xhr)
        }
    });
}
$(".submitter").each(function(){
    let spin = $('<span class="visually-hidden spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>');
    $(this).prepend(spin);
});
$(".submitter").click(function(e){
    e.preventDefault();
    let $this = $(this);
    let action_name = $this.text().trim();
    let ok = true;
    $this.parents("form").find("input,select,textarea").each(function(){
        if($(this).prop("required")&&!$(this).val()) ok = false;
    });
    if(!ok){
        show_modal("錯誤","部分資訊未填寫");
        return;
    }
    $this.parents("form").find("input,select,textarea").each(function(){
        if($(this).prop("required")&&$(this).prop("pattern")&&!$(this).val().match(RegExp($(this).prop("pattern")))) ok = false;
    });
    if(!ok||$this.parents("form")[0].onsubmit&&!$this.parents("form")[0].onsubmit()){
        show_modal("錯誤","輸入格式不正確");
        return;
    }
    $this.find("span").removeClass("visually-hidden");
    let modals = $this.parents(".modal");
    let modal = null;
    if(modals.length) modal = bootstrap.Modal.getOrCreateInstance(modals[0]);
    console.log(modal)
    fetching($this.parents("form").first()).then(function (response) {
        console.log(response);
        if(modal) modal.hide();
        $this.find("span").addClass("visually-hidden");
        response.text().then(function(text){
            let link = null;
            if(response.ok) {
                if(!!$this.data("redirect")) link = text;
                show_modal("成功","成功"+action_name, !$this.data("no-refresh"), $this.data("next") || link);
            }else if (response.status==500){
                show_modal("失敗", "伺服器內部錯誤，log uid="+text);
            }else {
                let msg = $this.data("msg-"+response.status);
                if(!msg&&response.status==400) msg = "輸入格式不正確"
                if(!msg&&response.status==403) msg = "您似乎沒有權限執行此操作"
                show_modal("失敗",msg?msg:"Error Code: " + response.status);
            }
        });
    });
});
var copyer = document.createElement("textarea");
document.body.appendChild(copyer);
$(copyer).hide();
$("pre.can-copy").each(function() {
    let p = $(this);
    let text = p.text();
    let copy = $('<button class="copy_btn">copy</button>');
    p.append(copy);
    p.css("position","relative");
    copy.click(function() {
        copyer.value = text;
        copyer.select();
        copyer.setSelectionRange(0, 99999);
        navigator.clipboard.writeText(copyer.value);
    });
});