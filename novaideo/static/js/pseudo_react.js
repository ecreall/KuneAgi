function nav_bar_component(data){
	$.each(data.components, function(index){
		var component_id = 'component-navbar-'+data.components[index]
		var original_components = $('#'+component_id)
		if (original_components.length > 0){
			var original_component = $(original_components[0])
			var new_component = null
			if (data.navbar_item_nb > 0){
				new_component = '<li class="menu-item" id="'+component_id+'">'
	            var ori_view_link =  $(original_component.find('a').first())
	            if (ori_view_link && ori_view_link.attr('href')){
	              var link_class = ori_view_link.attr('class')? ori_view_link.attr('class'): ''
	              new_component += '<a class="'+link_class+'" href="'+data.view_url+'">'
	            	
	            }else{
	            	new_component += '<a href="'+data.view_url+'">'
	            }
			    new_component +='<span class="hidden-xs">'+data.navbar_title+' <span class=" item-nb">'+data.navbar_item_nb
                    if (data.navbar_all_item_nb){
                    	new_component += '/'+data.navbar_all_item_nb
                    }
			    new_component +='</span></span>'
			    new_component +='<span class="visible-xs-inline-block action-icon '+data.navbar_icon+'"></span>'
			    new_component +='</a>'
			    new_component +='</li>'
			}else{
				new_component = '<li class="menu-item" id="'+component_id+'">'
	            new_component += '<a class="disabled">'
	            new_component +='<span class="hidden-xs">'+data.navbar_title+'</span>'
			    new_component +='<span class="visible-xs-inline-block action-icon '+data.navbar_icon+'"></span>'
			    new_component +='</a>'
			    new_component +='</li>'
			}
			if(new_component != null){
				original_component.replaceWith($(new_component))
			}
			
		}
	})
}

function footer_action_component(data){
	$.each(data.components, function(index){
		var component_id = 'component-footer-action-'+data.components[index]
		var original_components = $('[id="'+component_id+'"]')
		var actionlinks = $(original_components.parents('a.ajax-action'))
		$.each( original_components, function(index){
			var original_component = $(original_components[index])
			var new_component_id = data.has_opposit? 'component-footer-action-'+data.new_component_id:component_id
			var new_component = '<span id="'+new_component_id+'"><span class="footer-icon '+data.action_icon+'"></span> '+
			                    '<span class="hidden-xs"> '+data.action_title+' ('+data.action_item_nb+')</span></span>'
			if(new_component != null){
				original_component.replaceWith($(new_component))
				if (data.has_opposit){
                    $.each(actionlinks, function(actionindex){
                    	$(this).attr('data-actionid', data.opposit_action_id)
                    	$(this).attr('data-updateurl', data.opposit_actionurl_update)
                    	$(this).attr('data-after_exe_url', data.opposit_actionurl_after)
                    	$(this).attr('data-title', data.action_title)
                    	$(this).attr('data-icon', data.action_icon)

                    	$(this).data('actionid', data.opposit_action_id)
                    	$(this).data('updateurl', data.opposit_actionurl_update)
                    	$(this).data('after_exe_url', data.opposit_actionurl_after)
                    	$(this).data('title', data.action_title)
                    	$(this).data('icon', data.action_icon)

                    	$(this).attr('title', data.action_title)
                    	$(this).attr('id', data.opposit_action_id+'-btn')
                    })
				}

			}
		})
	})
}

function view_title_component(data){
    var url = window.location.href; 
	var is_mysupportsview = url.indexOf('/'+data.view_name+'') || url.indexOf('/@@'+data.view_name)  
	if(data.view_title && is_mysupportsview>=0){
		$($('.pontus-main .panel-title>h4').first()).text(data.view_title)
	}
}

function list_items_component(data){
    var url = window.location.href; 
	var is_mysupportsview = url.indexOf('/'+data.view_name+'') || url.indexOf('/@@'+data.view_name)   
	if(data.removed && is_mysupportsview>=0){
        data.search_item.remove()
	}
}

var pseudo_react_components = {
	'support_action': [nav_bar_component, view_title_component, list_items_component],
	'footer_action': [nav_bar_component, footer_action_component,
	                  view_title_component, list_items_component]
}

function update_components(data){
    var actionid = data.action_id
    var components_to_update = pseudo_react_components[actionid]
    $.each(components_to_update, function(index){
    	this(data)	
    })
}
