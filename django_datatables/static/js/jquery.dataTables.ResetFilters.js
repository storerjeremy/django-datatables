(function($) {
/*
 * Function: fnResetAllFilters
 * Purpose:  Reset all filters
 * Author:   http://www.datatables.net/forums/discussion/997/fnfilter-how-to-reset-all-filters-without-multiple-requests./p1
 */
$.fn.dataTableExt.oApi.fnResetAllFilters = function (oSettings, bDraw/*default true*/) {
    for(iCol = 0; iCol < oSettings.aoPreSearchCols.length; iCol++) {
    	oSettings.aoPreSearchCols[ iCol ].sSearch = '';
    }
    oSettings.oPreviousSearch.sSearch = '';
 
    if(typeof bDraw === 'undefined') bDraw = true;
    if(bDraw) this.fnDraw();

}}(jQuery));