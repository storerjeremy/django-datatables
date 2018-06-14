(function($) {
/*
 * Function: fnResetAll
 * Purpose:  Reset all filters and sorting
 * Author:   Alex Hayes (amalgamation of fnResetFilters and fnSortNeutral
 */
$.fn.dataTableExt.oApi.fnResetAll = function (oSettings, bDraw/*default true*/) {
    for(iCol = 0; iCol < oSettings.aoPreSearchCols.length; iCol++) {
    	oSettings.aoPreSearchCols[ iCol ].sSearch = '';
    }
    oSettings.oPreviousSearch.sSearch = '';
    
    /* Remove any current sorting */
    oSettings.aaSorting = [];
      
    /* Sort display arrays so we get them in numerical order */
    oSettings.aiDisplay.sort( function (x,y) {
        return x-y;
    });
    oSettings.aiDisplayMaster.sort( function (x,y) {
        return x-y;
    });
      
    if(typeof bDraw === 'undefined') bDraw = true;
    if(bDraw) oSettings.oApi._fnReDraw( oSettings );

}}(jQuery));