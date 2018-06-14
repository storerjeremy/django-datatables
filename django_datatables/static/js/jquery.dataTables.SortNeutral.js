(function($) {
/*
 * Function: fnSortNeutral
 * Purpose:  This function will restore the order in which data was read into a DataTable
 * Author:   Allan Jardine http://sprymedia.co.uk/
 * See:      http://datatables.net/plug-ins/api#fnSortNeutral
 */
$.fn.dataTableExt.oApi.fnSortNeutral = function ( oSettings )
{
    /* Remove any current sorting */
    oSettings.aaSorting = [];
      
    /* Sort display arrays so we get them in numerical order */
    oSettings.aiDisplay.sort( function (x,y) {
        return x-y;
    } );
    oSettings.aiDisplayMaster.sort( function (x,y) {
        return x-y;
    } );
      
    /* Redraw */
    oSettings.oApi._fnReDraw( oSettings );
}}(jQuery));