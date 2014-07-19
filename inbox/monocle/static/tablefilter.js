/*====================================================
	- HTML Table Filter Generator v1.6
	- By Max Guglielmi
	- mguglielmi.free.fr/scripts/TableFilter/?l=en
	- please do not change this comment
	- don't forget to give some credit... it's always
	good for the author
	- Special credit to Cedric Wartel and 
	cnx.claude@free.fr for contribution and 
	inspiration
=====================================================*/

// global vars
var TblId, SearchFlt, SlcArgs;
TblId = new Array(), SlcArgs = new Array();


function setFilterGrid(id)
/*====================================================
	- Checks if id exists and is a table
	- Then looks for additional params 
	- Calls fn that generates the grid
=====================================================*/
{	
	var tbl = grabEBI(id);
	var ref_row, fObj;
	if(tbl != null && tbl.nodeName.toLowerCase() == "table")
	{						
		if(arguments.length>1)
		{
			for(var i=0; i<arguments.length; i++)
			{
				var argtype = typeof arguments[i];
				
				switch(argtype.toLowerCase())
				{
					case "number":
						ref_row = arguments[i];
					break;
					case "object":
						fObj = arguments[i];
					break;
				}//switch
							
			}//for
		}//if
		
		ref_row == undefined ? ref_row=2 : ref_row=(ref_row+2);
		var ncells = getCellsNb(id,ref_row);
		tbl.tf_ncells = ncells;
		if(tbl.tf_ref_row==undefined) tbl.tf_ref_row = ref_row;
		tbl.tf_Obj = fObj;
		if( !hasGrid(id) ) AddGrid(id);		
	}//if tbl!=null
}

function AddGrid(id)
/*====================================================
	- adds a row containing the filtering grid
=====================================================*/
{	
	TblId.push(id);
	var t = grabEBI(id);
	var f = t.tf_Obj, n = t.tf_ncells;	
	var inpclass, fltgrid, displayBtn, btntext, enterkey;
	var modfilter_fn, display_allText, on_slcChange;
	var displaynrows, totrows_text, btnreset, btnreset_text;
	var sort_slc, displayPaging, pagingLength, displayLoader;
	var load_text, exactMatch, alternateBgs, colOperation;
	var rowVisibility, colWidth, bindScript;
	
	f!=undefined && f["grid"]==false ? fltgrid=false : fltgrid=true;//enables/disables filter grid
	f!=undefined && f["btn"]==true ? displayBtn=true : displayBtn=false;//show/hides filter's validation button
	f!=undefined && f["btn_text"]!=undefined ? btntext=f["btn_text"] : btntext="go";//defines button text
	f!=undefined && f["enter_key"]==false ? enterkey=false : enterkey=true;//enables/disables enter key
	f!=undefined && f["mod_filter_fn"] ? modfilter_fn=true : modfilter_fn=false;//defines alternative fn
	f!=undefined && f["display_all_text"]!=undefined ? display_allText=f["display_all_text"] : display_allText="";//defines 1st option text
	f!=undefined && f["on_change"]==false ? on_slcChange=false : on_slcChange=true;//enables/disables onChange event on combo-box 
	f!=undefined && f["rows_counter"]==true ? displaynrows=true : displaynrows=false;//show/hides rows counter
	f!=undefined && f["rows_counter_text"]!=undefined ? totrows_text=f["rows_counter_text"] : totrows_text="Displayed rows: ";//defines rows counter text
	f!=undefined && f["btn_reset"]==true ? btnreset=true : btnreset=false;//show/hides reset link
	f!=undefined && f["btn_reset_text"]!=undefined ? btnreset_text=f["btn_reset_text"] : btnreset_text="Reset";//defines reset text
	f!=undefined && f["sort_select"]==true ? sort_slc=true : sort_slc=false;//enables/disables select options sorting
	f!=undefined && f["paging"]==true ? displayPaging=true : displayPaging=false;//enables/disables table paging
	f!=undefined && f["paging_length"]!=undefined ? pagingLength=f["paging_length"] : pagingLength=10;//defines table paging length
	f!=undefined && f["loader"]==true ? displayLoader=true : displayLoader=false;//enables/disables loader
	f!=undefined && f["loader_text"]!=undefined ? load_text=f["loader_text"] : load_text="Loading...";//defines loader text
	f!=undefined && f["exact_match"]==true ? exactMatch=true : exactMatch=false;//enables/disbles exact match for search
	f!=undefined && f["alternate_rows"]==true ? alternateBgs=true : alternateBgs=false;//enables/disbles rows alternating bg colors
	f!=undefined && f["col_operation"] ? colOperation=true : colOperation=false;//enables/disbles column operation(sum,mean)
	f!=undefined && f["rows_always_visible"] ? rowVisibility=true : rowVisibility=false;//makes a row always visible
	f!=undefined && f["col_width"] ? colWidth=true : colWidth=false;//defines widths of columns
	f!=undefined && f["bind_script"] ? bindScript=true : bindScript=false;
	
	// props are added to table in order to be easily accessible from other fns
	t.tf_fltGrid			=	fltgrid;
	t.tf_displayBtn			= 	displayBtn;
	t.tf_btnText			=	btntext;
	t.tf_enterKey			= 	enterkey;
	t.tf_isModfilter_fn		= 	modfilter_fn;
	t.tf_display_allText 	= 	display_allText;
	t.tf_on_slcChange 		= 	on_slcChange;
	t.tf_rowsCounter 		= 	displaynrows;
	t.tf_rowsCounter_text	= 	totrows_text;
	t.tf_btnReset 			= 	btnreset;
	t.tf_btnReset_text 		= 	btnreset_text;
	t.tf_sortSlc 			=	sort_slc;
	t.tf_displayPaging 		= 	displayPaging;
	t.tf_pagingLength 		= 	pagingLength;
	t.tf_displayLoader		= 	displayLoader;
	t.tf_loadText			= 	load_text;
	t.tf_exactMatch 		= 	exactMatch;
	t.tf_alternateBgs		=	alternateBgs;
	t.tf_startPagingRow		= 	0;
	
	if(modfilter_fn) t.tf_modfilter_fn = f["mod_filter_fn"];// used by DetectKey fn

	if(fltgrid)
	{
		var fltrow = t.insertRow(0); //adds filter row
		fltrow.className = "fltrow";
		for(var i=0; i<n; i++)// this loop adds filters
		{
			var fltcell = fltrow.insertCell(i);
			//fltcell.noWrap = true;
			i==n-1 && displayBtn==true ? inpclass = "flt_s" : inpclass = "flt";
			
			if(f==undefined || f["col_"+i]==undefined || f["col_"+i]=="none") 
			{
				var inptype;
				(f==undefined || f["col_"+i]==undefined) ? inptype="text" : inptype="hidden";//show/hide input	
				var inp = createElm( "input",["id","flt"+i+"_"+id],["type",inptype],["class",inpclass] );					
				inp.className = inpclass;// for ie<=6
				fltcell.appendChild(inp);
				if(enterkey) inp.onkeypress = DetectKey;
			}
			else if(f["col_"+i]=="select")
			{
				var slc = createElm( "select",["id","flt"+i+"_"+id],["class",inpclass] );
				slc.className = inpclass;// for ie<=6
				fltcell.appendChild(slc);
				PopulateOptions(id,i);
				if(displayPaging)//stores arguments for GroupByPage() fn
				{
					var args = new Array();
					args.push(id); args.push(i); args.push(n);
					args.push(display_allText); args.push(sort_slc); args.push(displayPaging);
					SlcArgs.push(args);
				}
				if(enterkey) slc.onkeypress = DetectKey;
				if(on_slcChange) 
				{
					(!modfilter_fn) ? slc.onchange = function(){ Filter(id); } : slc.onchange = f["mod_filter_fn"];
				} 
			}
			
			if(i==n-1 && displayBtn==true)// this adds button
			{
				var btn = createElm(
										"input",
										["id","btn"+i+"_"+id],["type","button"],
										["value",btntext],["class","btnflt"] 
									);
				btn.className = "btnflt";
				
				fltcell.appendChild(btn);
				(!modfilter_fn) ? btn.onclick = function(){ Filter(id); } : btn.onclick = f["mod_filter_fn"];					
			}//if		
			
		}// for i		
	}//if fltgrid

	if(displaynrows || btnreset || displayPaging || displayLoader)
	{
		
		/*** div containing rows # displayer + reset btn ***/
		var infdiv = createElm( "div",["id","inf_"+id],["class","inf"] );
		infdiv.className = "inf";// setAttribute method for class attribute doesn't seem to work on ie<=6
		t.parentNode.insertBefore(infdiv, t);
		
		if(displaynrows)
		{
			/*** left div containing rows # displayer ***/
			var totrows;
			var ldiv = createElm( "div",["id","ldiv_"+id] );
			displaynrows ? ldiv.className = "ldiv" : ldiv.style.display = "none";
			displayPaging ? totrows = pagingLength : totrows = getRowsNb(id);
			
			var totrows_span = createElm( "span",["id","totrows_span_"+id],["class","tot"] ); // tot # of rows displayer
			totrows_span.className = "tot";//for ie<=6
			totrows_span.appendChild( createText(totrows) );
		
			var totrows_txt = createText(totrows_text);
			ldiv.appendChild(totrows_txt);
			ldiv.appendChild(totrows_span);
			infdiv.appendChild(ldiv);
		}
		
		if(displayLoader)
		{
			/*** div containing loader  ***/
			var loaddiv = createElm( "div",["id","load_"+id],["class","loader"] );
			loaddiv.className = "loader";// for ie<=6
			loaddiv.style.display = "none";
			loaddiv.appendChild( createText(load_text) );	
			infdiv.appendChild(loaddiv);
		}
				
		if(displayPaging)
		{
			/*** mid div containing paging displayer ***/
			var mdiv = createElm( "div",["id","mdiv_"+id] );
			displayPaging ? mdiv.className = "mdiv" : mdiv.style.display = "none";						
			infdiv.appendChild(mdiv);
			
			var start_row = t.tf_ref_row;
			var row = grabTag(t,"tr");
			var nrows = row.length;
			var npages = Math.ceil( (nrows - start_row)/pagingLength );//calculates page nb
			
			var slcPages = createElm( "select",["id","slcPages_"+id] );
			slcPages.onchange = function(){
				if(displayLoader) showLoader(id,"");
				t.tf_startPagingRow = this.value;
				GroupByPage(id);
				if(displayLoader) showLoader(id,"none");
			}
			
			var pgspan = createElm( "span",["id","pgspan_"+id] );
			grabEBI("mdiv_"+id).appendChild( createText(" Page ") );
			grabEBI("mdiv_"+id).appendChild(slcPages);
			grabEBI("mdiv_"+id).appendChild( createText(" of ") );
			pgspan.appendChild( createText(npages+" ") );
			grabEBI("mdiv_"+id).appendChild(pgspan);	
			
			for(var j=start_row; j<nrows; j++)//this sets rows to validRow=true
			{
				row[j].setAttribute("validRow","true");
			}//for j
			
			setPagingInfo(id);
			if(displayLoader) showLoader(id,"none");
		}
		
		if(btnreset && fltgrid)
		{
			/*** right div containing reset button **/	
			var rdiv = createElm( "div",["id","reset_"+id] );
			btnreset ? rdiv.className = "rdiv" : rdiv.style.display = "none";
			
			var fltreset = createElm( 	"a",
										["href","javascript:clearFilters('"+id+"');Filter('"+id+"');"] );
			fltreset.appendChild(createText(btnreset_text));
			rdiv.appendChild(fltreset);
			infdiv.appendChild(rdiv);
		}
		
	}//if displaynrows etc.
	
	if(colWidth)
	{
		t.tf_colWidth = f["col_width"];
		setColWidths(id);
	}
	
	if(alternateBgs && !displayPaging)
		setAlternateRows(id);
	
	if(colOperation)
	{
		t.tf_colOperation = f["col_operation"];
		setColOperation(id);
	}
	
	if(rowVisibility)
	{
		t.tf_rowVisibility = f["rows_always_visible"];
		if(displayPaging) setVisibleRows(id);
	}
	
	if(bindScript)
	{
		t.tf_bindScript = f["bind_script"];
		if(	t.tf_bindScript!=undefined &&
			t.tf_bindScript["target_fn"]!=undefined )
		{//calls a fn if defined  
			t.tf_bindScript["target_fn"].call(null,id);
		}
	}//if bindScript
}

function PopulateOptions(id,cellIndex)
/*====================================================
	- populates select
	- adds only 1 occurence of a value
=====================================================*/
{
	var t = grabEBI(id);
	var ncells = t.tf_ncells, opt0txt = t.tf_display_allText;
	var sort_opts = t.tf_sortSlc, paging = t.tf_displayPaging;
	var start_row = t.tf_ref_row;
	var row = grabTag(t,"tr");
	var OptArray = new Array();
	var optIndex = 0; // option index
	var currOpt = new Option(opt0txt,"",false,false); //1st option
	grabEBI("flt"+cellIndex+"_"+id).options[optIndex] = currOpt;
	
	for(var k=start_row; k<row.length; k++)
	{
		var cell = getChildElms(row[k]).childNodes;
		var nchilds = cell.length;
		var isPaged = row[k].getAttribute("paging");
		
		if(nchilds == ncells){// checks if row has exact cell #
			
			for(var j=0; j<nchilds; j++)// this loop retrieves cell data
			{
				if(cellIndex==j)
				{
					var cell_data = getCellText(cell[j]);
					// checks if celldata is already in array
					var isMatched = false;
					for(w in OptArray)
					{
						if( cell_data == OptArray[w] ) isMatched = true;
					}
					if(!isMatched) OptArray.push(cell_data);
				}//if cellIndex==j
			}//for j
		}//if
	}//for k
	
	if(sort_opts) OptArray.sort();
	for(y in OptArray)
	{
		optIndex++;
		var currOpt = new Option(OptArray[y],OptArray[y],false,false);
		grabEBI("flt"+cellIndex+"_"+id).options[optIndex] = currOpt;		
	}
		
}

function Filter(id)
/*====================================================
	- Filtering fn
	- gets search strings from SearchFlt array
	- retrieves data from each td in every single tr
	and compares to search string for current
	column
	- tr is hidden if all search strings are not 
	found
=====================================================*/
{	
	showLoader(id,"");
	SearchFlt = getFilters(id);
	var t = grabEBI(id);
	t.tf_Obj!=undefined ? fprops = t.tf_Obj : fprops = new Array();
	var SearchArgs = new Array();
	var ncells = getCellsNb(id);
	var totrows = getRowsNb(id), hiddenrows = 0;
	var ematch = t.tf_exactMatch;
	var showPaging = t.tf_displayPaging;
	
	for(var i=0; i<SearchFlt.length; i++)
		SearchArgs.push( (grabEBI(SearchFlt[i]).value).toLowerCase() );
	
	var start_row = t.tf_ref_row;
	var row = grabTag(t,"tr");
	
	for(var k=start_row; k<row.length; k++)
	{
		/*** if table already filtered some rows are not visible ***/
		if(row[k].style.display == "none") row[k].style.display = "";
		
		var cell = getChildElms(row[k]).childNodes;
		var nchilds = cell.length;

		if(nchilds == ncells)// checks if row has exact cell #
		{
			var cell_value = new Array();
			var occurence = new Array();
			var isRowValid = true;
				
			for(var j=0; j<nchilds; j++)// this loop retrieves cell data
			{
				var cell_data = getCellText(cell[j]).toLowerCase();
				cell_value.push(cell_data);
				
				if(SearchArgs[j]!="")
				{
					var num_cell_data = parseFloat(cell_data);
					
					if(/<=/.test(SearchArgs[j]) && !isNaN(num_cell_data)) // first checks if there is an operator (<,>,<=,>=)
					{
						num_cell_data <= parseFloat(SearchArgs[j].replace(/<=/,"")) ? occurence[j] = true : occurence[j] = false;
					}
					
					else if(/>=/.test(SearchArgs[j]) && !isNaN(num_cell_data))
					{
						num_cell_data >= parseFloat(SearchArgs[j].replace(/>=/,"")) ? occurence[j] = true : occurence[j] = false;
					}
					
					else if(/</.test(SearchArgs[j]) && !isNaN(num_cell_data))
					{
						num_cell_data < parseFloat(SearchArgs[j].replace(/</,"")) ? occurence[j] = true : occurence[j] = false;
					}
										
					else if(/>/.test(SearchArgs[j]) && !isNaN(num_cell_data))
					{
						num_cell_data > parseFloat(SearchArgs[j].replace(/>/,"")) ? occurence[j] = true : occurence[j] = false;
					}					
					
					else 
					{						
						// Improved by Cedric Wartel (cwl)
						// automatic exact match for selects and special characters are now filtered
						// modif cwl : exact match automatique sur les select
						var regexp;
						if(ematch || fprops["col_"+j]=="select") regexp = new RegExp('(^)'+regexpEscape(SearchArgs[j])+'($)',"gi");
						else regexp = new RegExp(regexpEscape(SearchArgs[j]),"gi");
						occurence[j] = regexp.test(cell_data);
					}
				}//if SearchArgs
			}//for j
			
			for(var z=0; z<ncells; z++)
			{
				if(SearchArgs[z]!="" && !occurence[z]) isRowValid = false;
			}//for t
			
		}//if
		
		if(!isRowValid)
		{ 
			row[k].style.display = "none"; hiddenrows++; 
			if( showPaging ) row[k].setAttribute("validRow","false");
		} else {
			row[k].style.display = ""; 
			if( showPaging ) row[k].setAttribute("validRow","true");
		}
		
	}// for k
	
	t.tf_nRows = parseInt( getRowsNb(id) )-hiddenrows;
	if( !showPaging ) applyFilterProps(id);//applies filter props after filtering process
	if( showPaging ){ t.tf_startPagingRow=0; setPagingInfo(id); }//starts paging process	
}

function setPagingInfo(id)
/*====================================================
	- Paging fn
	- calculates page # according to valid rows
	- refreshes paging select according to page #
	- Calls GroupByPage fn
=====================================================*/
{	
	var t = grabEBI(id);
	var start_row = parseInt( t.tf_ref_row );//filter start row
	var pagelength = t.tf_pagingLength;
	var row = grabTag(t,"tr");	
	var mdiv = grabEBI("mdiv_"+id);
	var slcPages = grabEBI("slcPages_"+id);
	var pgspan = grabEBI("pgspan_"+id);
	var nrows = 0;
	
	for(var j=start_row; j<row.length; j++)//counts rows to be grouped 
	{
		if(row[j].getAttribute("validRow") == "true") nrows++;
	}//for j
	
	var npg = Math.ceil( nrows/pagelength );//calculates page nb
	pgspan.innerHTML = npg; //refresh page nb span 
	slcPages.innerHTML = "";//select clearing shortcut
	
	if( npg>0 )
	{
		mdiv.style.visibility = "visible";
		for(var z=0; z<npg; z++)
		{
			var currOpt = new Option((z+1),z*pagelength,false,false);
			slcPages.options[z] = currOpt;
		}
	} else {/*** if no results paging select is hidden ***/
		mdiv.style.visibility = "hidden";
	}
	
	GroupByPage(id);
}

function GroupByPage(id)
/*====================================================
	- Paging fn
	- Displays current page rows
=====================================================*/
{
	showLoader(id,"");
	var t = grabEBI(id);
	var start_row = parseInt( t.tf_ref_row );//filter start row
	var pagelength = parseInt( t.tf_pagingLength );
	var paging_start_row = parseInt( t.tf_startPagingRow );//paging start row
	var paging_end_row = paging_start_row + pagelength;
	var row = grabTag(t,"tr");
	var nrows = 0;
	var validRows = new Array();//stores valid rows index
	
	for(var j=start_row; j<row.length; j++)
	//this loop stores valid rows index in validRows Array
	{
		var isRowValid = row[j].getAttribute("validRow");
		if(isRowValid=="true") validRows.push(j);
	}//for j

	for(h=0; h<validRows.length; h++)
	//this loop shows valid rows of current page
	{
		if( h>=paging_start_row && h<paging_end_row )
		{
			nrows++;
			row[ validRows[h] ].style.display = "";
		} else row[ validRows[h] ].style.display = "none";
	}//for h
	
	t.tf_nRows = parseInt(nrows);
	applyFilterProps(id);//applies filter props after filtering process
}

function applyFilterProps(id)
/*====================================================
	- checks fns that should be called
	after filtering and/or paging process
=====================================================*/
{
	t = grabEBI(id);
	var rowsCounter = t.tf_rowsCounter;
	var nRows = t.tf_nRows;
	var rowVisibility = t.tf_rowVisibility;
	var alternateRows = t.tf_alternateBgs;
	var colOperation = t.tf_colOperation;
	
	if( rowsCounter ) showRowsCounter( id,parseInt(nRows) );//refreshes rows counter
	if( rowVisibility ) setVisibleRows(id);//shows rows always visible
	if( alternateRows ) setAlternateRows(id);//alterning row colors
	if( colOperation  ) setColOperation(id);//makes operation on a col
	showLoader(id,"none");
}

function hasGrid(id)
/*====================================================
	- checks if table has a filter grid
	- returns a boolean
=====================================================*/
{
	var r = false, t = grabEBI(id);
	if(t != null && t.nodeName.toLowerCase() == "table")
	{
		for(i in TblId)
		{
			if(id == TblId[i]) r = true;
		}// for i
	}//if
	return r;
}

function getCellsNb(id,nrow)
/*====================================================
	- returns number of cells in a row
	- if nrow param is passed returns number of cells 
	of that specific row
=====================================================*/
{
  	var t = grabEBI(id);
	var tr;
	if(nrow == undefined) tr = grabTag(t,"tr")[0];
	else  tr = grabTag(t,"tr")[nrow];
	var n = getChildElms(tr);
	return n.childNodes.length;
}

function getRowsNb(id)
/*====================================================
	- returns total nb of filterable rows starting 
	from reference row if defined
=====================================================*/
{
	var t = grabEBI(id);
	var s = t.tf_ref_row;
	var ntrs = grabTag(t,"tr").length;
	return parseInt(ntrs-s);
}

function getFilters(id)
/*====================================================
	- returns an array containing filters ids
	- Note that hidden filters are also returned
=====================================================*/
{
	var SearchFltId = new Array();
	var t = grabEBI(id);
	var tr = grabTag(t,"tr")[0];
	var enfants = tr.childNodes;
	if(t.tf_fltGrid)
	{
		for(var i=0; i<enfants.length; i++) 
			SearchFltId.push(enfants[i].firstChild.getAttribute("id"));		
	}
	return SearchFltId;
}

function clearFilters(id)
/*====================================================
	- clears grid filters
=====================================================*/
{
	SearchFlt = getFilters(id);
	for(i in SearchFlt) grabEBI(SearchFlt[i]).value = "";
}

function showLoader(id,p)
/*====================================================
	- displays/hides loader div
=====================================================*/
{
	var loader = grabEBI("load_"+id);
	if(loader != null && p=="none")
		setTimeout("grabEBI('load_"+id+"').style.display = '"+p+"'",150);
	else if(loader != null && p!="none") loader.style.display = p;
}

function showRowsCounter(id,p)
/*====================================================
	- Shows total number of filtered rows
=====================================================*/
{
	var totrows = grabEBI("totrows_span_"+id);
	if(totrows != null && totrows.nodeName.toLowerCase() == "span" ) 
		totrows.innerHTML = p;
}

function getChildElms(n)
/*====================================================
	- checks passed node is a ELEMENT_NODE nodeType=1
	- removes TEXT_NODE nodeType=3  
=====================================================*/
{
	if(n.nodeType == 1)
	{
		var enfants = n.childNodes;
		for(var i=0; i<enfants.length; i++)
		{
			var child = enfants[i];
			if(child.nodeType == 3) n.removeChild(child);
		}
		return n;	
	}
}

function getCellText(n)
/*====================================================
	- returns text + text of child nodes of a cell
=====================================================*/
{
	var s = "";
	var enfants = n.childNodes;
	for(var i=0; i<enfants.length; i++)
	{
		var child = enfants[i];
		if(child.nodeType == 3) s+= child.data;
		else s+= getCellText(child);
	}
	return s;
}

function getColValues(id,colindex,num)
/*====================================================
	- returns an array containing cell values of
	a column
	- needs following args:
		- filter id (string)
		- column index (number)
		- a boolean set to true if we want only 
		numbers to be returned
=====================================================*/
{
	var t = grabEBI(id);
	var row = grabTag(t,"tr");
	var nrows = row.length;
	var start_row = parseInt( t.tf_ref_row );//filter start row
	var ncells = getCellsNb( id,start_row );
	var colValues = new Array();
	
	for(var i=start_row; i<nrows; i++)//iterates rows
	{
		var cell = getChildElms(row[i]).childNodes;
		var nchilds = cell.length;
	
		if(nchilds == ncells)// checks if row has exact cell #
		{
			for(var j=0; j<nchilds; j++)// this loop retrieves cell data
			{
				if(j==colindex && row[i].style.display=="" )
				{
					var cell_data = getCellText( cell[j] ).toLowerCase();
					(num) ? colValues.push( parseFloat(cell_data) ) : colValues.push( cell_data );
				}//if j==k
			}//for j
		}//if nchilds == ncells
	}//for i
	return colValues;	
}

function setColWidths(id)
/*====================================================
	- sets widths of columns
=====================================================*/
{
	if( hasGrid(id) )
	{
		var t = grabEBI(id);
		t.style.tableLayout = "fixed";
		var colWidth = t.tf_colWidth;
		var start_row = parseInt( t.tf_ref_row );//filter start row
		var row = grabTag(t,"tr")[0];
		var ncells = getCellsNb(id,start_row);
		for(var i=0; i<colWidth.length; i++)
		{
			for(var k=0; k<ncells; k++)
			{
				cell = row.childNodes[k];
				if(k==i) cell.style.width = colWidth[i];
			}//var k
		}//for i
	}//if hasGrid
}

function setVisibleRows(id)
/*====================================================
	- makes a row always visible
=====================================================*/
{
	if( hasGrid(id) )
	{
		var t = grabEBI(id);		
		var row = grabTag(t,"tr");
		var nrows = row.length;
		var showPaging = t.tf_displayPaging;
		var visibleRows = t.tf_rowVisibility;
		for(var i=0; i<visibleRows.length; i++)
		{
			if(visibleRows[i]<=nrows)//row index cannot be > nrows
			{
				if(showPaging)
					row[ visibleRows[i] ].setAttribute("validRow","true");
				row[ visibleRows[i] ].style.display = "";
			}//if
		}//for i
	}//if hasGrid
}

function setAlternateRows(id)
/*====================================================
	- alternates row colors for better readability
=====================================================*/
{
	if( hasGrid(id) )
	{
		var t = grabEBI(id);		
		var row = grabTag(t,"tr");
		var nrows = row.length;
		var start_row = parseInt( t.tf_ref_row );//filter start row
		var visiblerows = new Array();
		for(var i=start_row; i<nrows; i++)//visible rows are stored in visiblerows array
			if( row[i].style.display=="" ) visiblerows.push(i);
		
		for(var j=0; j<visiblerows.length; j++)//alternates bg color
			(j % 2 == 0) ? row[ visiblerows[j] ].className = "even" : row[ visiblerows[j] ].className = "odd";
		
	}//if hasGrid
}

function setColOperation(id)
/*====================================================
	- Calculates values of a column
	- params are stored in 'colOperation' table's
	attribute
		- colOperation["id"] contains ids of elements 
		showing result (array)
		- colOperation["col"] contains index of 
		columns (array)
		- colOperation["operation"] contains operation
		type (array, values: sum, mean)
		- colOperation["write_method"] array defines 
		which method to use for displaying the 
		result (innerHTML, setValue, createTextNode).
		Note that innerHTML is the default value.
		
	!!! to be optimised
=====================================================*/
{
	if( hasGrid(id) )
	{
		var t = grabEBI(id);
		var labelId = t.tf_colOperation["id"];
		var colIndex = t.tf_colOperation["col"];
		var operation = t.tf_colOperation["operation"];
		var outputType =  t.tf_colOperation["write_method"];
		var precision = 2;//decimal precision
		
		if( (typeof labelId).toLowerCase()=="object" 
			&& (typeof colIndex).toLowerCase()=="object" 
			&& (typeof operation).toLowerCase()=="object" )
		{
			var row = grabTag(t,"tr");
			var nrows = row.length;
			var start_row = parseInt( t.tf_ref_row );//filter start row
			var ncells = getCellsNb( id,start_row );
			var colvalues = new Array();
						
			for(var k=0; k<colIndex.length; k++)//this retrieves col values
			{
				colvalues.push( getColValues(id,colIndex[k],true) );			
			}//for k
			
			for(var i=0; i<colvalues.length; i++)
			{
				var result=0, nbvalues=0;
				for(var j=0; j<colvalues[i].length; j++ )
				{
					var cvalue = colvalues[i][j];
					if( !isNaN(cvalue) )
					{
						switch( operation[i].toLowerCase() )
						{
							case "sum":
								result += parseFloat( cvalue );
							break;
							case "mean":
								nbvalues++;
								result += parseFloat( cvalue );
							break;
							//add cases for other operations
						}//switch
					}
				}//for j
				
				switch( operation[i].toLowerCase() )
				{
					case "mean":
						result = result/nbvalues;
					break;
				}
				
				if(outputType != undefined && (typeof outputType).toLowerCase()=="object")
				//if outputType is defined
				{
					result = result.toFixed( precision );
					if( grabEBI( labelId[i] )!=undefined )
					{
						switch( outputType[i].toLowerCase() )
						{
							case "innerhtml":
								grabEBI( labelId[i] ).innerHTML = result;
							break;
							case "setvalue":
								grabEBI( labelId[i] ).value = result;
							break;
							case "createtextnode":
								var oldnode = grabEBI( labelId[i] ).firstChild;
								var txtnode = createText( result );
								grabEBI( labelId[i] ).replaceChild( txtnode,oldnode );
							break;
							//other cases could be added
						}//switch
					}
				} else {
					try
					{
						grabEBI( labelId[i] ).innerHTML = result.toFixed( precision );
					} catch(e){ }//catch
				}//else
				
			}//for i

		}//if typeof
	}//if hasGrid
}

function grabEBI(id)
/*====================================================
	- this is just a getElementById shortcut
=====================================================*/
{
	return document.getElementById( id );
}

function grabTag(obj,tagname)
/*====================================================
	- this is just a getElementsByTagName shortcut
=====================================================*/
{
	return obj.getElementsByTagName( tagname );
}

function regexpEscape(s)
/*====================================================
	- escapes special characters [\^$.|?*+() 
	for regexp
	- Many thanks to Cedric Wartel for this fn
=====================================================*/
{
	// traite les caractères spéciaux [\^$.|?*+()
	//remplace le carctère c par \c
	function escape(e)
	{
		a = new RegExp('\\'+e,'g');
		s = s.replace(a,'\\'+e);
	}

	chars = new Array('\\','[','^','$','.','|','?','*','+','(',')');
	//chars.each(escape); // no prototype framework here...
	for(e in chars) escape(chars[e]);
	return s;
}

function createElm(elm)
/*====================================================
	- returns an html element with its attributes
	- accepts the following params:
		- a string defining the html element 
		to create
		- an undetermined # of arrays containing the
		couple "attribute name","value" ["id","myId"]
=====================================================*/
{
	var el = document.createElement( elm );		
	if(arguments.length>1)
	{
		for(var i=0; i<arguments.length; i++)
		{
			var argtype = typeof arguments[i];
			switch( argtype.toLowerCase() )
			{
				case "object":
					if( arguments[i].length==2 )
					{							
						el.setAttribute( arguments[i][0],arguments[i][1] );
					}//if array length==2
				break;
			}//switch
		}//for i
	}//if args
	return el;	
}

function createText(node)
/*====================================================
	- this is just a document.createTextNode shortcut
=====================================================*/
{
	return document.createTextNode( node );
}

function DetectKey(e)
/*====================================================
	- common fn that detects return key for a given
	element (onkeypress attribute on input)
=====================================================*/
{
	var evt=(e)?e:(window.event)?window.event:null;
	if(evt)
	{
		var key=(evt.charCode)?evt.charCode:
			((evt.keyCode)?evt.keyCode:((evt.which)?evt.which:0));
		if(key=="13")
		{
			var cid, leftstr, tblid, CallFn, Match;		
			cid = this.getAttribute("id");
			leftstr = this.getAttribute("id").split("_")[0];
			tblid = cid.substring(leftstr.length+1,cid.length);
			t = grabEBI(tblid);
			(t.tf_isModfilter_fn) ? t.tf_modfilter_fn.call() : Filter(tblid);
		}//if key
	}//if evt	
}

function importScript(scriptName,scriptPath)
{
	var isImported = false; 
	var scripts = grabTag(document,"script");

	for (var i=0; i<scripts.length; i++)
	{
		if(scripts[i].src.match(scriptPath))
		{ 
			isImported = true;	
			break;
		}
	}

	if( !isImported )//imports script if not available
	{
		var head = grabTag(document,"head")[0];
		var extScript = createElm(	"script",
									["id",scriptName],
									["type","text/javascript"],
									["src",scriptPath]	);
		head.appendChild(extScript);
	}
}//fn importScript



/*====================================================
	- Below a collection of public functions 
	for developement purposes
	- all public methods start with prefix 'TF_'
	- These methods can be removed safely if not
	needed
=====================================================*/

function TF_GetFilterIds()
/*====================================================
	- returns an array containing filter grids ids
=====================================================*/
{
	try{ return TblId }
	catch(e){ alert('TF_GetFilterIds() fn: could not retrieve any ids'); }
}

function TF_HasGrid(id)
/*====================================================
	- checks if table has a filter grid
	- returns a boolean
=====================================================*/
{
	return hasGrid(id);
}

function TF_GetFilters(id)
/*====================================================
	- returns an array containing filters ids of a
	specified grid
=====================================================*/
{
	try
	{
		var flts = getFilters(id);
		return flts;
	} catch(e) {
		alert('TF_GetFilters() fn: table id not found');
	}
	
}

function TF_GetStartRow(id)
/*====================================================
	- returns starting row index for filtering
	process
=====================================================*/
{
	try
	{
		var t = grabEBI(id);
		return t.tf_ref_row;
	} catch(e) {
		alert('TF_GetStartRow() fn: table id not found');
	}
}

function TF_GetColValues(id,colindex,num)
/*====================================================
	- returns an array containing cell values of
	a column
	- needs following args:
		- filter id (string)
		- column index (number)
		- a boolean set to true if we want only 
		numbers to be returned
=====================================================*/
{
	if( hasGrid(id) )
	{
		return getColValues(id,colindex,num);
	}//if TF_HasGrid
	else alert('TF_GetColValues() fn: table id not found');
}

function TF_Filter(id)
/*====================================================
	- filters a table
=====================================================*/
{
	var t = grabEBI(id);
	if( TF_HasGrid(id) ) Filter(id);
	else alert('TF_Filter() fn: table id not found');
}

function TF_RemoveFilterGrid(id)
/*====================================================
	- removes a filter grid
=====================================================*/
{
	if( TF_HasGrid(id) )
	{
		var t = grabEBI(id);
		clearFilters(id);
				
		if(grabEBI("inf_"+id)!=null)
		{
			t.parentNode.removeChild(t.previousSibling);
		}
		// remove paging here
		var row = grabTag(t,"tr");
		
		for(var j=0; j<row.length; j++)
		//this loop shows all rows and removes validRow attribute
		{			
			row[j].style.display = "";
			try
			{ 
				if( row[j].hasAttribute("validRow") ) 
					row[j].removeAttribute("validRow");
			} //ie<=6 doesn't support hasAttribute method
			catch(e){
				for( var x = 0; x < row[j].attributes.length; x++ ) 
				{
					if( row[j].attributes[x].nodeName.toLowerCase()=="validrow" ) 
						row[j].removeAttribute("validRow");
				}//for x
			}//catch(e)
		}//for j		
		
		if( t.tf_alternateBgs )//removes alterning row colors
		{
			for(var k=0; k<row.length; k++)
			//this loop removes bg className
			{
				row[k].className = "";
			}
		}
		
		if(t.tf_fltGrid) t.deleteRow(0);
		for(i in TblId)//removes grid id value from array
			if(id == TblId[i]) TblId.splice(i,1);
		
	}//if TF_HasGrid
	else alert('TF_RemoveFilterGrid() fn: table id not found');
}

function TF_ClearFilters(id)
/*====================================================
	- clears grid filters only, table is not filtered
=====================================================*/
{
	if( TF_HasGrid(id) ) clearFilters(id);
	else alert('TF_ClearFilters() fn: table id not found');
}

function TF_SetFilterValue(id,index,searcharg)
/*====================================================
	- Inserts value in a specified filter
	- Params:
		- id: table id (string)
		- index: filter column index (numeric value)
		- searcharg: search string
=====================================================*/
{
	if( TF_HasGrid(id) )
	{
		var flts = getFilters(id);
		for(i in flts)
		{
			if( i==index ) grabEBI(flts[i]).value = searcharg;
		}
	} else {
		alert('TF_SetFilterValue() fn: table id not found');
	}
}




/*====================================================
	- bind an external script fns
	- fns below do not belong to filter grid script 
	and are used to interface with external 
	autocomplete script found at the following URL:
	http://www.codeproject.com/jscript/jsactb.asp
	(credit to zichun) 
	- fns used to merge filter grid with external
	scripts
=====================================================*/
var colValues = new Array();

function setAutoComplete(id)
{
	var t = grabEBI(id);
	var bindScript = t.tf_bindScript;
	var scriptName = bindScript["name"];
	var scriptPath = bindScript["path"];
	initAutoComplete();
	
	function initAutoComplete()
	{
		var filters = TF_GetFilters(id);
		for(var i=0; i<filters.length; i++)
		{
			if( grabEBI(filters[i]).nodeName.toLowerCase()=="input")
			{
				colValues.push( getColValues(id,i) );	
			} else colValues.push( '' );
		}//for i

		try{ actb( grabEBI(filters[0]), colValues[0] ); }
		catch(e){ alert(scriptPath + " script may not be loaded"); }

	}//fn
}